"""이미지 alt 텍스트 생성 (SEO).

이미지 설명을 검색 친화적인 짧은 alt 문구로 변환한다. LLM 사용이 가능하면 자연스러운 문구를,
실패/비활성 시 설명을 그대로 다듬어 사용한다.
"""

from __future__ import annotations

from ..config import Config

_MAX_LEN = 80


def make_alt_text(config: Config, description: str) -> str:
    """간단·안전한 alt 텍스트. (LLM 없이도 동작)

    의료광고 안전을 위해 효과 보장/과장 표현은 넣지 않는다.
    """
    desc = description.strip().rstrip(".")
    # 토큰 설명에서 불필요한 접두 제거
    for prefix in ("이미지", "사진", "그림", "일러스트", "인포그래픽"):
        if desc.startswith(prefix):
            desc = desc[len(prefix):].lstrip(" :-")
    specialty = config.get("blog.specialty", "피부과")
    alt = f"{specialty} 정보 이미지 - {desc}" if desc else f"{specialty} 정보 이미지"
    return alt[:_MAX_LEN]
