"""텍스트 → 인포그래픽 자동 생성 (Pillow).

본문 이미지 설명을 바탕으로 제목 + 불릿 포인트 카드 이미지를 만든다. 외부 API 불필요.
불릿 내용은 LLM 으로 보강할 수 있으나(선택), 기본은 설명을 간단히 카드화한다.
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:  # Pillow 미설치 시
    Image = None  # type: ignore

from ..config import Config

# 카드 스타일 (스킨케어 톤의 부드러운 색)
_BG = (244, 247, 246)
_BAR = (84, 168, 156)
_TITLE_COLOR = (33, 51, 48)
_TEXT_COLOR = (60, 72, 70)
_WIDTH = 1080
_HEIGHT = 720
_MARGIN = 70


def render_infographic(
    config: Config,
    description: str,
    out_path: Path,
    *,
    bullets: Sequence[str] | None = None,
) -> Path:
    """설명을 카드형 인포그래픽 PNG 로 렌더링해 경로를 반환한다."""
    if Image is None:
        raise RuntimeError("Pillow 가 설치되지 않았습니다. requirements.txt 설치 필요.")

    title, points = _derive_content(description, bullets)
    clinic = config.get("blog.clinic_name", "")

    img = Image.new("RGB", (_WIDTH, _HEIGHT), _BG)
    draw = ImageDraw.Draw(img)

    # 좌측 강조 바
    draw.rectangle([0, 0, 16, _HEIGHT], fill=_BAR)

    title_font = _load_font(48)
    text_font = _load_font(34)
    small_font = _load_font(24)

    # 제목 (줄바꿈 처리)
    y = _MARGIN
    for line in _wrap(title, title_font, _WIDTH - 2 * _MARGIN, draw):
        draw.text((_MARGIN, y), line, font=title_font, fill=_TITLE_COLOR)
        y += 60
    y += 20
    draw.line([(_MARGIN, y), (_WIDTH - _MARGIN, y)], fill=_BAR, width=3)
    y += 40

    # 불릿
    for point in points:
        draw.ellipse([_MARGIN, y + 12, _MARGIN + 14, y + 26], fill=_BAR)
        for i, line in enumerate(
            _wrap(point, text_font, _WIDTH - 2 * _MARGIN - 40, draw)
        ):
            draw.text((_MARGIN + 34, y), line, font=text_font, fill=_TEXT_COLOR)
            y += 46
        y += 14
        if y > _HEIGHT - 90:
            break

    # 하단 안내(의료법): 정보 제공 목적 명시
    footer = "※ 본 이미지는 일반적 정보 제공용이며 진단·치료는 전문의 상담이 필요합니다."
    if clinic:
        footer = f"{clinic}  |  " + footer
    draw.text((_MARGIN, _HEIGHT - 50), footer, font=small_font, fill=_TEXT_COLOR)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path)
    return out_path


def _derive_content(
    description: str, bullets: Sequence[str] | None
) -> tuple[str, list[str]]:
    """설명에서 제목과 불릿을 만든다."""
    if bullets:
        return description, list(bullets)
    # '제목: a, b, c' 또는 '제목 - a / b' 같은 단순 패턴 분해
    title = description
    points: list[str] = []
    for sep in (":", "-"):
        if sep in description:
            head, _, tail = description.partition(sep)
            title = head.strip()
            points = [p.strip() for p in tail.replace("/", ",").split(",") if p.strip()]
            break
    if not points:
        points = [description]
    return title, points


def _load_font(size: int):
    """한글 가능한 폰트 로드. 시스템에 없으면 기본 폰트로 폴백."""
    candidates = [
        "C:/Windows/Fonts/malgun.ttf",       # Windows 맑은 고딕
        "C:/Windows/Fonts/malgunbd.ttf",
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",  # Linux
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",        # macOS
    ]
    for path in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except Exception:  # noqa: BLE001
                continue
    return ImageFont.load_default()


def _wrap(text: str, font, max_width: int, draw) -> list[str]:
    """글자 단위 줄바꿈(한글은 단어 경계가 약하므로 글자 기준)."""
    lines: list[str] = []
    current = ""
    for ch in text:
        trial = current + ch
        width = draw.textlength(trial, font=font)
        if width > max_width and current:
            lines.append(current)
            current = ch
        else:
            current = trial
    if current:
        lines.append(current)
    return lines
