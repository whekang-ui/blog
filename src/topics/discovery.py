"""트렌드 기반 주제 자동 발굴.

1) Claude 웹검색으로 "요즘 피부과적으로 사람들이 찾는" 이슈/계절성/신규 시술 등을 조사해
   주제 후보 + 후보별 핵심 검색 키워드를 뽑는다.
2) 네이버 데이터랩으로 그 키워드들의 상대 검색량을 교차검증해 수요 점수(demand_score)를 매긴다.
3) 점수 높은 순으로 주제 후보를 반환한다.

데이터랩 키가 없으면 웹검색 결과만으로 점수를 매긴다(LLM 추정 수요).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from ..config import Config
from ..llm import LLM
from .datalab import DataLab

_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "topics": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "topic": {"type": "string"},
                    "primary_keyword": {"type": "string"},
                    "keywords": {"type": "array", "items": {"type": "string"}},
                    "search_intent": {
                        "type": "string",
                        "enum": ["정보형", "비교형", "후기형", "예방형"],
                    },
                    "rationale": {"type": "string"},
                    "est_demand": {"type": "number"},
                },
                "required": [
                    "topic",
                    "primary_keyword",
                    "keywords",
                    "search_intent",
                    "rationale",
                    "est_demand",
                ],
            },
        }
    },
    "required": ["topics"],
}


@dataclass
class TopicCandidate:
    topic: str
    primary_keyword: str
    keywords: list[str]
    search_intent: str
    rationale: str
    demand_score: float
    sources: list[str] = field(default_factory=list)


def discover_topics(config: Config, *, count: int = 8) -> list[TopicCandidate]:
    """수요 높은 피부과 블로그 주제 후보를 발굴한다."""
    llm = LLM(config)
    specialty = config.get("blog.specialty", "피부과")
    today = date.today().isoformat()

    research = llm.web_search(
        f"오늘은 {today}이다. 한국 {specialty} 환자들이 '요즘' 가장 많이 검색하고 궁금해하는 "
        f"주제를 조사하라. 다음을 반영할 것: (1) 현재 계절/시기에 늘어나는 피부 고민, "
        f"(2) 최근 이슈가 된 시술·성분·제품, (3) 네이버/구글에서 검색량이 늘고 있는 키워드. "
        f"근거가 되는 출처를 함께 제시하라.",
        system=(
            "너는 한국 의료 콘텐츠 마케팅 리서처다. 추측이 아니라 검색 결과에 근거해 답하라. "
            "허위·과장 정보는 배제한다."
        ),
    )

    candidates_raw = llm.generate_json(
        "아래 리서치 내용을 바탕으로, 네이버 블로그에 올릴 피부과 주제 후보를 "
        f"{count}개 제안하라. 각 후보에 대해 주제, 대표 검색키워드(primary_keyword), "
        "연관 키워드 목록, 검색의도, 선정 근거(rationale), 0~100 사이의 예상 수요(est_demand)를 "
        f"채워라. 의료광고 심의에 걸릴 만한 과장 주제는 피한다.\n\n[리서치]\n{research}",
        schema=_SCHEMA,
        system="너는 한국 피부과 콘텐츠 전략가다. 실제 검색 수요가 높은 주제를 고른다.",
    )

    candidates: list[TopicCandidate] = []
    for item in candidates_raw.get("topics", []):
        candidates.append(
            TopicCandidate(
                topic=item["topic"],
                primary_keyword=item["primary_keyword"],
                keywords=item.get("keywords", []),
                search_intent=item.get("search_intent", "정보형"),
                rationale=item.get("rationale", ""),
                demand_score=float(item.get("est_demand", 50.0)),
            )
        )

    _cross_check_with_datalab(config, candidates)
    candidates.sort(key=lambda c: c.demand_score, reverse=True)
    return candidates


def _cross_check_with_datalab(
    config: Config, candidates: list[TopicCandidate]
) -> None:
    """데이터랩 상대지수로 demand_score 를 보정(LLM 추정과 50:50 가중)."""
    datalab = DataLab(config)
    if not datalab.enabled or not candidates:
        return
    primary = [c.primary_keyword for c in candidates]
    trends = {t.keyword: t.avg_ratio for t in datalab.keyword_demand(primary)}
    if not trends:
        return
    max_ratio = max(trends.values()) or 1.0
    for c in candidates:
        ratio = trends.get(c.primary_keyword)
        if ratio is None:
            continue
        datalab_score = (ratio / max_ratio) * 100.0
        c.demand_score = round((c.demand_score + datalab_score) / 2.0, 1)
        c.sources.append(f"datalab:{ratio}")
