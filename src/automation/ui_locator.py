"""에디터 버튼 위치 인식 (이미지 매칭).

좌표 하드코딩 대신, 사용자가 assets/ 에 저장한 버튼 캡처 PNG 를 화면에서 찾는다.
opencv 가 있으면 confidence 매칭을 쓰고, 없으면 정확 매칭으로 폴백한다.

필요한 캡처 파일(예):
  assets/title_area.png      제목 입력 영역
  assets/body_area.png       본문 입력 영역
  assets/image_button.png    사진 첨부 버튼
  assets/tag_area.png        태그 입력 영역
  assets/publish_button.png  발행 버튼
  assets/schedule_toggle.png 예약 발행 토글 (선택)
"""

from __future__ import annotations

from pathlib import Path

try:
    import pyautogui
    _HAS_GUI = True
except Exception:  # noqa: BLE001
    pyautogui = None  # type: ignore
    _HAS_GUI = False

from ..config import Config


class ElementNotFound(RuntimeError):
    pass


class UiLocator:
    def __init__(self, config: Config) -> None:
        self.assets = config.assets_dir()
        self.confidence = config.get("automation.match_confidence", 0.8)

    def find(self, asset_name: str) -> tuple[int, int]:
        """assets/<asset_name> 버튼의 화면 중심 좌표를 반환."""
        if not _HAS_GUI:
            raise ElementNotFound("GUI 환경이 아닙니다 (pyautogui 불가).")
        path = self.assets / asset_name
        if not path.exists():
            raise ElementNotFound(
                f"버튼 캡처 파일이 없습니다: {path}. README 의 1회 셋업을 참고해 캡처를 넣으세요."
            )
        try:
            point = pyautogui.locateCenterOnScreen(
                str(path), confidence=self.confidence
            )
        except TypeError:
            # opencv 미설치 시 confidence 미지원 → 정확 매칭
            point = pyautogui.locateCenterOnScreen(str(path))
        if point is None:
            raise ElementNotFound(
                f"화면에서 '{asset_name}' 버튼을 찾지 못했습니다. 에디터가 열려 있는지, "
                f"캡처 이미지가 현재 화면과 같은지 확인하세요."
            )
        return int(point.x), int(point.y)

    def exists(self, asset_name: str) -> bool:
        try:
            self.find(asset_name)
            return True
        except ElementNotFound:
            return False


def required_assets() -> list[str]:
    return [
        "title_area.png",
        "body_area.png",
        "image_button.png",
        "tag_area.png",
        "publish_button.png",
    ]


def missing_assets(config: Config) -> list[str]:
    """필요한데 아직 없는 캡처 파일 목록."""
    assets_dir = config.assets_dir()
    return [name for name in required_assets() if not (assets_dir / name).exists()]
