"""이미지 준비: AI 비임상 이미지 + 인포그래픽 자동생성 + 사용자 사진 + alt 텍스트.

본문의 [[IMAGE:설명]] 토큰 각각을 실제 이미지 파일에 매핑한다. 매핑 우선순위(기본):
1) 사용자가 user_photos/ 에 넣고 지정한 사진
2) 인포그래픽 자동생성(설명이 '정보/과정/주의사항/비교' 등 정보성일 때)
3) AI 비임상 이미지 생성(개념/일러스트/스킨케어 모델 느낌) — IMAGE_API 키가 있을 때만
4) 위가 모두 불가하면 인포그래픽으로 폴백
"""

from __future__ import annotations

from dataclasses import dataclass

from ..config import Config
from .ai_image import generate_ai_image
from .alt_text import make_alt_text
from .infographic import render_infographic

_INFOGRAPHIC_HINTS = ("정보", "과정", "단계", "주의", "비교", "표", "체크", "요약", "통계")


@dataclass
class PreparedImage:
    description: str
    path: str
    kind: str  # 'user' | 'infographic' | 'ai'
    alt_text: str
    position: int


def prepare_media(
    config: Config,
    descriptions: list[str],
    *,
    user_photo_map: dict[int, str] | None = None,
) -> list[PreparedImage]:
    """본문 이미지 설명 목록을 실제 이미지로 변환한다.

    user_photo_map: {본문 이미지 인덱스(0부터): 사용자 사진 파일경로}
    """
    user_photo_map = user_photo_map or {}
    out_dir = config.media_output_dir()
    ai_enabled = config.get("images.ai_images_enabled", False) and config.secrets.has_image_api
    info_enabled = config.get("images.infographics_enabled", True)

    prepared: list[PreparedImage] = []
    for idx, desc in enumerate(descriptions):
        # 1) 사용자가 직접 지정한 사진
        if idx in user_photo_map:
            path = user_photo_map[idx]
            prepared.append(
                PreparedImage(desc, path, "user", make_alt_text(config, desc), idx)
            )
            continue

        # 2) 정보성 설명이면 인포그래픽
        if info_enabled and _looks_informational(desc):
            path = render_infographic(config, desc, out_dir / f"info_{idx}.png")
            prepared.append(
                PreparedImage(desc, str(path), "infographic", make_alt_text(config, desc), idx)
            )
            continue

        # 3) AI 비임상 이미지
        if ai_enabled:
            path = generate_ai_image(config, desc, out_dir / f"ai_{idx}.png")
            if path:
                prepared.append(
                    PreparedImage(desc, str(path), "ai", make_alt_text(config, desc), idx)
                )
                continue

        # 4) 폴백: 인포그래픽
        if info_enabled:
            path = render_infographic(config, desc, out_dir / f"info_{idx}.png")
            prepared.append(
                PreparedImage(desc, str(path), "infographic", make_alt_text(config, desc), idx)
            )

    return prepared


def _looks_informational(description: str) -> bool:
    return any(h in description for h in _INFOGRAPHIC_HINTS)
