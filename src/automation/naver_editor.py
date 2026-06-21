"""네이버 스마트에디터 ONE 구동 (OS 레벨 입력).

이미 로그인된 Chrome 의 글쓰기 페이지를 대상으로, 사람처럼 제목/본문/이미지/태그를 입력하고
즉시 또는 예약 발행한다. 좌표 대신 assets/ 의 버튼 캡처를 이미지 매칭으로 찾는다.

dry_run=True 면 실제 입력 없이 '동작 계획'만 출력한다(헤드리스/테스트 환경에서 검증용).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ..config import Config
from ..images import PreparedImage
from .humanize import Humanizer, gui_available
from .ui_locator import UiLocator

_IMAGE_TOKEN_RE = re.compile(r"\[\[IMAGE:.*?\]\]")

try:
    import pygetwindow as gw
except Exception:  # noqa: BLE001
    gw = None  # type: ignore


@dataclass
class PublishOptions:
    visibility: str = "private"      # 'private'(비공개) | 'public'(공개)
    scheduled_at: str | None = None  # ISO 문자열이면 네이티브 예약발행 시도
    dry_run: bool = False


@dataclass
class Segment:
    """본문을 텍스트/이미지 조각으로 분해한 단위."""

    kind: str  # 'text' | 'image'
    text: str = ""
    image: PreparedImage | None = None


def format_schedule(
    scheduled_at: str, date_fmt: str, time_fmt: str
) -> tuple[str, str] | None:
    """ISO 예약시각 문자열을 (날짜문자열, 시간문자열)로 변환. 파싱 실패 시 None.

    네이버 예약 UI 의 날짜/시간 입력 포맷은 환경마다 달라 config 로 지정한다.
    예: date_fmt="%Y.%m.%d", time_fmt="%H:%M"
    """
    try:
        dt = datetime.fromisoformat(scheduled_at)
    except ValueError:
        return None
    return dt.strftime(date_fmt), dt.strftime(time_fmt)


def build_segments(body: str, images: list[PreparedImage]) -> list[Segment]:
    """[[IMAGE:...]] 토큰 위치 기준으로 본문을 텍스트/이미지 조각으로 분해한다.

    이미지는 본문에 나온 순서대로 images 리스트와 1:1 매핑한다.
    """
    segments: list[Segment] = []
    last = 0
    img_iter = iter(images)
    for m in _IMAGE_TOKEN_RE.finditer(body):
        text = body[last:m.start()].strip()
        if text:
            segments.append(Segment("text", text=text))
        image = next(img_iter, None)
        if image is not None:
            segments.append(Segment("image", image=image))
        last = m.end()
    tail = body[last:].strip()
    if tail:
        segments.append(Segment("text", text=tail))
    return segments


class NaverEditor:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.humanizer = Humanizer(
            min_delay=config.get("automation.min_action_delay_sec", 0.5),
            max_delay=config.get("automation.max_action_delay_sec", 2.5),
        )
        self.locator = UiLocator(config)

    # ---- public ---------------------------------------------------------
    def publish(
        self,
        title: str,
        body: str,
        tags: list[str],
        images: list[PreparedImage],
        options: PublishOptions,
    ) -> list[str]:
        """글을 발행(또는 예약/임시저장)한다. 수행한 동작 로그를 반환한다."""
        segments = build_segments(body, images)
        plan = self._make_plan(title, segments, tags, options)

        if options.dry_run or not gui_available():
            # 실제 입력 없이 계획만 반환 (테스트/검증)
            return plan

        self._focus_browser()
        self._enter_title(title)
        self._enter_body(segments)
        self._enter_tags(tags)
        self._finalize(options)
        return plan

    # ---- steps ----------------------------------------------------------
    def _focus_browser(self) -> None:
        if gw is None:
            return
        for w in gw.getAllWindows():
            if "Chrome" in (w.title or ""):
                try:
                    w.activate()
                except Exception:  # noqa: BLE001
                    pass
                break
        self.humanizer.pause()

    def _enter_title(self, title: str) -> None:
        x, y = self.locator.find("title_area.png")
        self.humanizer.move_click(x, y)
        self.humanizer.paste_text(title)

    def _enter_body(self, segments: list[Segment]) -> None:
        x, y = self.locator.find("body_area.png")
        self.humanizer.move_click(x, y)
        for seg in segments:
            if seg.kind == "text":
                paragraphs = seg.text.split("\n")
                self.humanizer.type_paragraphs(paragraphs)
                self.humanizer.press("enter")
            elif seg.kind == "image" and seg.image:
                self._attach_image(seg.image.path)

    def _attach_image(self, path: str) -> None:
        ix, iy = self.locator.find("image_button.png")
        self.humanizer.move_click(ix, iy)
        # OS 파일 열기 대화상자에 절대경로 입력 후 Enter
        self.humanizer.pause(1.0)
        self.humanizer.paste_text(str(Path(path).resolve()))
        self.humanizer.press("enter")
        self.humanizer.pause(1.5)  # 업로드 대기

    def _enter_tags(self, tags: list[str]) -> None:
        if not tags or not self.locator.exists("tag_area.png"):
            return
        x, y = self.locator.find("tag_area.png")
        self.humanizer.move_click(x, y)
        for tag in tags:
            self.humanizer.paste_text(tag.lstrip("#"))
            self.humanizer.press("enter")

    def _finalize(self, options: PublishOptions) -> None:
        x, y = self.locator.find("publish_button.png")
        self.humanizer.move_click(x, y)
        # 발행 옵션 패널에서 예약 설정(캡처가 있을 때만 자동화)
        if options.scheduled_at:
            self._set_schedule(options.scheduled_at)
        # 최종 발행 확정 버튼(있으면)
        if self.locator.exists("confirm_button.png"):
            cx, cy = self.locator.find("confirm_button.png")
            self.humanizer.move_click(cx, cy)

    def _set_schedule(self, scheduled_at: str) -> None:
        """예약 토글을 켜고 날짜/시간 필드에 값을 입력한다.

        schedule_toggle/date/time 캡처가 모두 있을 때만 날짜·시간을 자동 입력한다.
        토글만 있으면 토글까지만 수행(이후 사용자가 직접 시각 지정).
        """
        if not self.locator.exists("schedule_toggle.png"):
            return
        sx, sy = self.locator.find("schedule_toggle.png")
        self.humanizer.move_click(sx, sy)

        date_fmt = self.config.get("automation.schedule_date_format", "%Y.%m.%d")
        time_fmt = self.config.get("automation.schedule_time_format", "%H:%M")
        formatted = format_schedule(scheduled_at, date_fmt, time_fmt)
        if not formatted:
            return
        date_str, time_str = formatted
        if self.locator.exists("schedule_date.png"):
            dx, dy = self.locator.find("schedule_date.png")
            self.humanizer.move_click(dx, dy)
            self.humanizer.paste_text(date_str)
        if self.locator.exists("schedule_time.png"):
            tx, ty = self.locator.find("schedule_time.png")
            self.humanizer.move_click(tx, ty)
            self.humanizer.paste_text(time_str)

    # ---- plan (dry-run) -------------------------------------------------
    def _make_plan(
        self,
        title: str,
        segments: list[Segment],
        tags: list[str],
        options: PublishOptions,
    ) -> list[str]:
        plan = [
            "[1] Chrome 글쓰기 창 포커스",
            f"[2] 제목 입력(클립보드): {title}",
            "[3] 본문 입력:",
        ]
        n_text = n_img = 0
        for seg in segments:
            if seg.kind == "text":
                n_text += 1
                preview = seg.text.replace("\n", " ")[:40]
                plan.append(f"    - 텍스트 단락: {preview}...")
            elif seg.image:
                n_img += 1
                plan.append(
                    f"    - 이미지 첨부[{seg.image.kind}]: {seg.image.path} "
                    f"(alt: {seg.image.alt_text})"
                )
        plan.append(f"[4] 태그 {len(tags)}개 입력: {', '.join(tags)}")
        vis = "비공개" if options.visibility == "private" else "공개"
        if options.scheduled_at:
            date_fmt = self.config.get("automation.schedule_date_format", "%Y.%m.%d")
            time_fmt = self.config.get("automation.schedule_time_format", "%H:%M")
            formatted = format_schedule(options.scheduled_at, date_fmt, time_fmt)
            plan.append(f"[5] 발행 버튼 클릭 → 예약 토글 ON")
            if formatted:
                date_str, time_str = formatted
                plan.append(f"    - 날짜 입력: {date_str}")
                plan.append(f"    - 시간 입력: {time_str}")
            plan.append(f"[6] 예약 발행 확정({vis}) @ {options.scheduled_at}")
        else:
            plan.append(f"[5] 즉시 발행({vis})")
        plan.append(f"(요약: 텍스트 {n_text}블록, 이미지 {n_img}개)")
        return plan
