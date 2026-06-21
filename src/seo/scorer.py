"""SEO 점수 산출.

네이버 검색 품질(C-Rank: 출처 신뢰도, DIA/DIA+: 문서 품질·경험성)과 2026 트렌드 기준을
규칙으로 점수화한다. 100점 만점, 항목별 감점 사유와 개선 제안을 함께 낸다.

규칙 기반이라 LLM 호출 없이 빠르게 반복 평가할 수 있다(재생성 피드백 루프용).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..content.generator import GeneratedPost
from ..topics.discovery import TopicCandidate

_HEADING_RE = re.compile(r"^##\s+", re.MULTILINE)
_IMAGE_RE = re.compile(r"\[\[IMAGE:.*?\]\]")


@dataclass
class SeoCheck:
    name: str
    passed: bool
    score: float
    max_score: float
    detail: str


@dataclass
class SeoReport:
    score: float
    checks: list[SeoCheck] = field(default_factory=list)

    @property
    def failed_suggestions(self) -> list[str]:
        return [c.detail for c in self.checks if not c.passed]

    def to_dict(self) -> dict:
        return {
            "score": self.score,
            "checks": [c.__dict__ for c in self.checks],
        }


def score_post(
    post: GeneratedPost,
    topic: TopicCandidate,
    *,
    min_chars: int = 1500,
    min_images: int = 3,
) -> SeoReport:
    """글의 SEO 점수를 산출한다."""
    checks: list[SeoCheck] = []
    body = post.body
    plain = _IMAGE_RE.sub("", body)
    primary = topic.primary_keyword.strip()

    # 1) 제목에 대표 키워드 포함 + 앞부분 배치 (15점)
    title = post.title
    if primary and primary in title:
        pos = title.find(primary)
        early = pos <= max(1, len(title) // 2)
        checks.append(
            SeoCheck(
                "제목 키워드",
                True,
                15.0 if early else 10.0,
                15.0,
                "OK" if early else "대표 키워드를 제목 더 앞쪽으로 배치 권장.",
            )
        )
    else:
        checks.append(
            SeoCheck("제목 키워드", False, 0.0, 15.0,
                     f"제목에 대표 키워드 '{primary}' 를 포함하세요.")
        )

    # 2) 본문 분량 (20점)
    n = len(plain)
    if n >= min_chars:
        checks.append(SeoCheck("본문 분량", True, 20.0, 20.0, f"{n}자 (충분)"))
    else:
        ratio = max(0.0, n / min_chars)
        checks.append(
            SeoCheck("본문 분량", False, round(20.0 * ratio, 1), 20.0,
                     f"본문이 {n}자로 짧습니다. 최소 {min_chars}자 이상으로 늘리세요.")
        )

    # 3) 소제목 구조 (15점)
    headings = len(_HEADING_RE.findall(body))
    if headings >= 3:
        checks.append(SeoCheck("소제목 구조", True, 15.0, 15.0, f"## 소제목 {headings}개"))
    else:
        checks.append(
            SeoCheck("소제목 구조", False, round(15.0 * headings / 3, 1), 15.0,
                     "'## ' 소제목을 3개 이상 사용해 구조화하세요.")
        )

    # 4) 이미지 자리 (15점)
    images = len(_IMAGE_RE.findall(body))
    if images >= min_images:
        checks.append(SeoCheck("이미지", True, 15.0, 15.0, f"이미지 자리 {images}개"))
    else:
        checks.append(
            SeoCheck("이미지", False, round(15.0 * images / min_images, 1), 15.0,
                     f"[[IMAGE:...]] 이미지 자리를 {min_images}개 이상 배치하세요.")
        )

    # 5) 키워드 자연 반복 (10점) — 과최적화 페널티 포함
    kw_count = plain.count(primary) if primary else 0
    density = kw_count / max(1, n / 1000)  # 1000자당 등장 횟수
    if 1 <= kw_count and density <= 12:
        checks.append(SeoCheck("키워드 빈도", True, 10.0, 10.0,
                               f"대표 키워드 {kw_count}회 (자연)"))
    elif kw_count == 0:
        checks.append(SeoCheck("키워드 빈도", False, 0.0, 10.0,
                               "본문에 대표 키워드를 자연스럽게 포함하세요."))
    else:
        checks.append(SeoCheck("키워드 빈도", False, 4.0, 10.0,
                               "키워드가 과도하게 반복됩니다(스팸 위험). 줄이세요."))

    # 6) 가독성 — 평균 문단 길이 (10점)
    paragraphs = [p for p in plain.split("\n") if p.strip()]
    long_paras = [p for p in paragraphs if len(p) > 250]
    if paragraphs and len(long_paras) / len(paragraphs) <= 0.2:
        checks.append(SeoCheck("가독성", True, 10.0, 10.0, "문단이 짧고 읽기 쉬움"))
    else:
        checks.append(
            SeoCheck("가독성", False, 4.0, 10.0,
                     "긴 문단이 많습니다. 2~4문장으로 끊어 모바일 가독성을 높이세요.")
        )

    # 7) 태그 (5점)
    if 8 <= len(post.tags) <= 15:
        checks.append(SeoCheck("태그", True, 5.0, 5.0, f"태그 {len(post.tags)}개"))
    else:
        checks.append(
            SeoCheck("태그", False, 2.0, 5.0, "연관 해시태그 8~15개를 권장합니다.")
        )

    # 8) 마무리 안내 (10점) — 요약 + 전문의 상담 안내
    has_consult = any(k in plain for k in ("전문의", "상담", "진료", "병원 방문"))
    if has_consult:
        checks.append(SeoCheck("마무리 안내", True, 10.0, 10.0, "상담 안내 포함"))
    else:
        checks.append(
            SeoCheck("마무리 안내", False, 0.0, 10.0,
                     "마지막에 '정확한 진단·치료는 전문의 상담' 안내를 넣으세요.")
        )

    total = round(sum(c.score for c in checks), 1)
    return SeoReport(score=total, checks=checks)
