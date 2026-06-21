"""제목/본문/태그 생성.

TopicCandidate(주제+키워드+검색의도)를 받아 SEO·의료광고 규칙을 반영한 글을 생성한다.
본문에는 이미지 자리표시자 [[IMAGE:...]] 가 포함된다.
SEO 점수 미달 시 optimizer 가 주는 피드백으로 재생성하는 것도 지원한다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..config import Config
from ..llm import LLM
from ..topics.discovery import TopicCandidate
from .prompts import IMAGE_TOKEN_PREFIX, IMAGE_TOKEN_SUFFIX, system_prompt

_META_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "title": {"type": "string"},
        "tags": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["title", "tags"],
}

_IMAGE_RE = re.compile(
    re.escape(IMAGE_TOKEN_PREFIX) + r"(.*?)" + re.escape(IMAGE_TOKEN_SUFFIX)
)


@dataclass
class GeneratedPost:
    title: str
    body: str
    tags: list[str] = field(default_factory=list)

    @property
    def char_count(self) -> int:
        """이미지 토큰을 제외한 순수 본문 글자 수."""
        return len(_IMAGE_RE.sub("", self.body))

    def image_descriptions(self) -> list[str]:
        return _IMAGE_RE.findall(self.body)


def extract_image_descriptions(body: str) -> list[str]:
    """저장된 본문에서 [[IMAGE:...]] 설명 목록을 추출한다."""
    return _IMAGE_RE.findall(body or "")


def generate_post(
    config: Config,
    topic: TopicCandidate,
    *,
    feedback: str | None = None,
) -> GeneratedPost:
    """글을 생성한다. feedback 이 주어지면 그 개선점을 반영해 재작성한다."""
    llm = LLM(config)
    system = system_prompt(config)
    target = config.get("content.target_chars", 2200)
    min_chars = config.get("content.min_chars", 1500)

    keywords = ", ".join(topic.keywords) or topic.primary_keyword
    feedback_block = (
        f"\n\n[이전 버전 개선 요청]\n{feedback}\n위 피드백을 반드시 반영해 다시 작성하라."
        if feedback
        else ""
    )

    body_prompt = (
        f"주제: {topic.topic}\n"
        f"대표 검색키워드: {topic.primary_keyword}\n"
        f"연관 키워드: {keywords}\n"
        f"검색의도: {topic.search_intent}\n"
        f"목표 분량: 약 {target}자 (최소 {min_chars}자 이상)\n\n"
        "위 조건으로 네이버 블로그 본문을 작성하라. 소제목은 '## ' 로 시작한다. "
        f"이미지가 들어갈 자리에는 {IMAGE_TOKEN_PREFIX}설명{IMAGE_TOKEN_SUFFIX} 토큰을 "
        "본문 흐름에 맞게 3개 이상 넣어라(예: 개념 일러스트, 인포그래픽, 스킨케어 이미지). "
        "마지막에 핵심 요약과 전문의 상담 안내를 포함하라. 본문만 출력하라."
        f"{feedback_block}"
    )
    body = llm.generate_text(body_prompt, system=system, max_tokens=8000)

    meta = llm.generate_json(
        f"다음 블로그 본문에 어울리는, 검색 클릭을 유도하되 과장 없는 제목 1개와 "
        f"네이버 해시태그 8~12개를 만들어라. 대표 키워드 '{topic.primary_keyword}' 를 제목 "
        f"앞부분에 자연스럽게 포함한다.\n\n[본문]\n{body[:3000]}",
        schema=_META_SCHEMA,
        system=system,
    )

    return GeneratedPost(
        title=meta.get("title", topic.topic),
        body=body,
        tags=meta.get("tags", topic.keywords),
    )
