"""사람처럼 보이는 동작 유틸.

탐지 회피 및 안전을 위해: 동작 사이 랜덤 딜레이, 곡선/완급 있는 마우스 이동, 한글은 클립보드
붙여넣기, FAILSAFE(마우스를 좌상단으로 빼면 즉시 중단) 활성화.
"""

from __future__ import annotations

import random
import time

try:
    import pyautogui
    import pyperclip
    pyautogui.FAILSAFE = True  # 마우스 좌상단 이동 시 중단
    _HAS_GUI = True
except Exception:  # noqa: BLE001 - 헤드리스/미설치 환경
    pyautogui = None  # type: ignore
    pyperclip = None  # type: ignore
    _HAS_GUI = False


class GuiUnavailable(RuntimeError):
    pass


def _require_gui() -> None:
    if not _HAS_GUI:
        raise GuiUnavailable(
            "pyautogui/pyperclip 를 사용할 수 없습니다 (GUI 없는 환경이거나 미설치). "
            "Windows 데스크톱에서 실행하고 requirements.txt 를 설치하세요."
        )


class Humanizer:
    def __init__(self, min_delay: float = 0.5, max_delay: float = 2.5) -> None:
        self.min_delay = min_delay
        self.max_delay = max_delay

    def pause(self, scale: float = 1.0) -> None:
        time.sleep(random.uniform(self.min_delay, self.max_delay) * scale)

    def move_click(self, x: int, y: int) -> None:
        """곡선 완급 있는 이동 후 클릭."""
        _require_gui()
        duration = random.uniform(0.3, 0.9)
        pyautogui.moveTo(x, y, duration=duration, tween=pyautogui.easeInOutQuad)
        self.pause(0.4)
        pyautogui.click()
        self.pause(0.5)

    def paste_text(self, text: str) -> None:
        """한글 안전 입력: 클립보드 복사 후 Ctrl+V."""
        _require_gui()
        pyperclip.copy(text)
        self.pause(0.3)
        pyautogui.hotkey("ctrl", "v")
        self.pause(0.6)

    def type_paragraphs(self, paragraphs: list[str]) -> None:
        """본문을 단락별로 붙여넣되 사이에 사람같은 딜레이와 Enter 를 넣는다."""
        _require_gui()
        for i, para in enumerate(paragraphs):
            if not para.strip():
                pyautogui.press("enter")
                self.pause(0.3)
                continue
            self.paste_text(para)
            if i < len(paragraphs) - 1:
                pyautogui.press("enter")
                self.pause(0.5)

    def hotkey(self, *keys: str) -> None:
        _require_gui()
        pyautogui.hotkey(*keys)
        self.pause(0.4)

    def press(self, key: str) -> None:
        _require_gui()
        pyautogui.press(key)
        self.pause(0.3)


def gui_available() -> bool:
    return _HAS_GUI
