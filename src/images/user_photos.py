"""사용자 제공 사진 관리.

사용자가 user_photos/ 디렉터리에 넣은 이미지를 나열하고, 본문 이미지 자리(인덱스)에 매핑하는
것을 돕는다. 실제 매핑(어느 자리에 어떤 사진)은 review 단계에서 사용자가 지정한다.

의료법 주의: 환자 임상사진(시술 전후 포함)은 반드시 환자 동의를 받은 본인 촬영본만 사용해야 하며,
그 책임은 사용자(의료진)에게 있다. 이 모듈은 파일 관리만 담당한다.
"""

from __future__ import annotations

from pathlib import Path

from ..config import Config

_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def list_user_photos(config: Config) -> list[Path]:
    """user_photos 디렉터리의 이미지 파일을 이름순으로 반환."""
    photo_dir = config.user_photo_dir()
    return sorted(
        p for p in photo_dir.iterdir()
        if p.is_file() and p.suffix.lower() in _IMAGE_EXTS
    )


def build_photo_map(
    photos: list[Path], assignments: dict[int, int]
) -> dict[int, str]:
    """{본문 이미지 인덱스: 사진 목록 인덱스} → {본문 인덱스: 파일경로} 로 변환.

    assignments 예: {0: 2}  -> 본문 첫 이미지 자리에 photos[2] 사용.
    """
    result: dict[int, str] = {}
    for body_idx, photo_idx in assignments.items():
        if 0 <= photo_idx < len(photos):
            result[body_idx] = str(photos[photo_idx])
    return result
