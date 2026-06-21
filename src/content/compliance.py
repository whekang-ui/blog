"""의료광고(의료법) 컴플라이언스 점검.

2단계로 점검한다:
1) 규칙 기반 — 금지/과장 표현(완치, 100%, 부작용 없음, 최고 등)을 정규식으로 빠르게 탐지.
2) LLM 재검 — 규칙으로 못 잡는 맥락상 위반(치료효과 보장, 환자 유인성, 비포애프터 보장 등)을
   Claude 로 재검토.

이미지에 대해서는 'AI 생성 가짜 임상/시술 전후/환자 사진' 여부를 점검한다(의료법상 금지).
결과는 경고 목록으로 반환하며, 사람이 발행 전 검토한다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..config import Config
from ..llm import LLM

# (정규식, 사람이 읽을 설명) — 한국어 의료광고에서 흔한 위반 표현
_BANNED_PATTERNS: list[tuple[str, str]] = [
    (r"완치", "치료효과 단정('완치')"),
    (r"100\s*%|백\s*퍼센트", "효과/안전 단정('100%')"),
    (r"부작용\s*(이)?\s*(전혀\s*)?없", "부작용 없음 단정"),
    (r"무조건|확실히\s*(낫|효과)", "효과 보장 표현"),
    (r"최고|최상|유일|국내\s*1\s*위|업계\s*1\s*위", "최상급/비교우위 과장"),
    (r"가장\s*효과", "비교우위 과장('가장 효과적')"),
    (r"영구|평생\s*(유지|지속)", "영구 효과 단정"),
    (r"즉시\s*(완전|완벽)", "즉효 단정"),
]

_AI_IMAGE_FORBIDDEN = [
    "환자", "시술 전", "시술 후", "비포", "애프터", "before", "after",
    "병변", "수술 장면", "치료 결과", "실제 사례",
]

_LLM_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "violations": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "severity": {"type": "string", "enum": ["high", "medium", "low"]},
                    "issue": {"type": "string"},
                    "excerpt": {"type": "string"},
                    "suggestion": {"type": "string"},
                },
                "required": ["severity", "issue", "excerpt", "suggestion"],
            },
        }
    },
    "required": ["violations"],
}


@dataclass
class Warning:
    severity: str
    issue: str
    excerpt: str = ""
    suggestion: str = ""
    source: str = "rule"  # 'rule' | 'llm' | 'image'


@dataclass
class ComplianceReport:
    warnings: list[Warning] = field(default_factory=list)

    @property
    def has_high(self) -> bool:
        return any(w.severity == "high" for w in self.warnings)

    @property
    def ok(self) -> bool:
        return not self.warnings

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "has_high": self.has_high,
            "warnings": [w.__dict__ for w in self.warnings],
        }


def check_rules(text: str) -> list[Warning]:
    """규칙 기반 빠른 점검."""
    warnings: list[Warning] = []
    for pattern, desc in _BANNED_PATTERNS:
        for m in re.finditer(pattern, text):
            start = max(0, m.start() - 15)
            end = min(len(text), m.end() + 15)
            warnings.append(
                Warning(
                    severity="high",
                    issue=desc,
                    excerpt="..." + text[start:end].replace("\n", " ") + "...",
                    suggestion="단정·과장 표현을 '개인차가 있을 수 있다'는 식의 중립 표현으로 수정.",
                    source="rule",
                )
            )
    return warnings


def check_llm(config: Config, title: str, body: str) -> list[Warning]:
    """LLM 재검 — 맥락상 위반 탐지."""
    llm = LLM(config)
    result = llm.generate_json(
        "다음 한국 피부과 블로그 글이 의료법(의료광고 규정)을 위반할 소지가 있는지 점검하라. "
        "치료효과 보장, 환자 유인성(할인·이벤트 유도), 비포애프터 보장, 부작용 은폐, 객관적 "
        "근거 없는 최상급 표현, 검증되지 않은 효능 주장 등을 찾는다. 위반이 없으면 빈 배열을 "
        f"반환하라.\n\n[제목]\n{title}\n\n[본문]\n{body[:6000]}",
        schema=_LLM_SCHEMA,
        system="너는 한국 의료광고 사전심의 경험이 있는 컴플라이언스 검수자다. 보수적으로 본다.",
    )
    return [
        Warning(
            severity=v.get("severity", "medium"),
            issue=v.get("issue", ""),
            excerpt=v.get("excerpt", ""),
            suggestion=v.get("suggestion", ""),
            source="llm",
        )
        for v in result.get("violations", [])
    ]


def check_image_descriptions(descriptions: list[str]) -> list[Warning]:
    """AI 이미지 설명에 임상/환자/전후 사진 의도가 있는지 점검."""
    warnings: list[Warning] = []
    for desc in descriptions:
        low = desc.lower()
        for bad in _AI_IMAGE_FORBIDDEN:
            if bad.lower() in low:
                warnings.append(
                    Warning(
                        severity="high",
                        issue="AI 임상/환자/전후 사진 생성 시도 (의료법 위반 소지)",
                        excerpt=desc,
                        suggestion="실제 임상사진은 환자 동의를 받아 직접 촬영본만 사용. "
                        "AI 이미지는 비임상 개념/일러스트로 대체.",
                        source="image",
                    )
                )
                break
    return warnings


def run_compliance(
    config: Config,
    title: str,
    body: str,
    image_descriptions: list[str] | None = None,
    *,
    use_llm: bool = True,
) -> ComplianceReport:
    """전체 컴플라이언스 점검을 실행한다."""
    report = ComplianceReport()
    report.warnings.extend(check_rules(f"{title}\n{body}"))
    report.warnings.extend(check_image_descriptions(image_descriptions or []))
    if use_llm:
        try:
            report.warnings.extend(check_llm(config, title, body))
        except Exception:  # noqa: BLE001 - LLM 실패해도 규칙 결과는 반환
            report.warnings.append(
                Warning(
                    severity="low",
                    issue="LLM 컴플라이언스 재검 실패 (수동 검토 권장)",
                    source="llm",
                )
            )
    return report
