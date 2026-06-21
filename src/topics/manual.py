"""사용자가 직접 주제를 입력하는 경로.

주제 문자열을 받아, 핵심 키워드를 LLM 으로 보강(선택)한 뒤 큐에 넣을 수 있는 형태로 만든다.
키워드 보강은 SEO 품질을 위해 권장되지만, 오프라인/키 없음 상황에서는 생략 가능하다.
"""

from __future__ import annotations

from ..config import Config
from ..llm import LLM
from .discovery import TopicCandidate

_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "primary_keyword": {"type": "string"},
        "keywords": {"type": "array", "items": {"type": "string"}},
        "search_intent": {
            "type": "string",
            "enum": ["정보형", "비교형", "후기형", "예방형"],
        },
    },
    "required": ["primary_keyword", "keywords", "search_intent"],
}


def build_manual_topic(
    config: Config, topic: str, *, enrich: bool = True
) -> TopicCandidate:
    """수동 주제를 TopicCandidate 로 변환한다."""
    topic = topic.strip()
    if not enrich:
        return TopicCandidate(
            topic=topic,
            primary_keyword=topic,
            keywords=[topic],
            search_intent="정보형",
            rationale="사용자 직접 입력",
            demand_score=50.0,
        )

    llm = LLM(config)
    specialty = config.get("blog.specialty", "피부과")
    result = llm.generate_json(
        f"'{topic}' 라는 {specialty} 블로그 주제에 대해, 네이버 검색 SEO 에 유리한 "
        "대표 검색키워드(primary_keyword), 연관 키워드 목록(keywords), 검색의도(search_intent)를 "
        "정하라. 실제 사람들이 검색할 법한 자연스러운 표현을 사용한다.",
        schema=_SCHEMA,
        system="너는 한국 피부과 콘텐츠 SEO 전략가다.",
    )
    return TopicCandidate(
        topic=topic,
        primary_keyword=result.get("primary_keyword", topic),
        keywords=result.get("keywords", [topic]),
        search_intent=result.get("search_intent", "정보형"),
        rationale="사용자 직접 입력 (키워드 자동 보강)",
        demand_score=60.0,
    )
