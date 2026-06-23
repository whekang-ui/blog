"""설정 로딩: config.json + .env 를 합쳐 하나의 Config 객체로 제공한다.

config.example.json 을 config.json 으로 복사해 값을 채우고, .env.example 을 .env 로
복사해 API 키를 넣는다. 이 모듈은 두 소스를 읽어 점(.) 경로로 접근 가능한 설정을 만든다.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv
except ImportError:  # dotenv 미설치 환경에서도 import 자체는 깨지지 않게
    def load_dotenv(*_args: Any, **_kwargs: Any) -> bool:  # type: ignore
        return False


def _project_root() -> Path:
    """프로젝트 루트 디렉터리.

    - 일반 실행: 이 파일의 두 단계 위 (src/ 의 부모).
    - PyInstaller .exe(동결): exe 가 놓인 폴더. 이렇게 해야 config.json/.env/assets/blog.db
      를 exe 옆에서 찾는다(임시 추출폴더 _MEIxxxx 가 아니라).
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


# 프로젝트 루트 (일반 실행 시 src/ 의 부모, .exe 동결 시 exe 폴더)
ROOT = _project_root()


def _bundle_dir() -> Path | None:
    """PyInstaller 번들 내부 폴더(_MEIPASS). 동결이 아니면 None.

    빌드 시 spec 의 datas 로 넣은 .env/config.json 이 여기에 들어간다(번들 폴백용).
    """
    base = getattr(sys, "_MEIPASS", None)
    return Path(base) if base else None


def _resource_candidates(name: str) -> list[Path]:
    """설정 파일 탐색 후보 경로(우선순위 순).

    1) exe/프로젝트 폴더 옆 (사용자가 직접 편집 가능 — 우선)
    2) 번들 내부(_MEIPASS) (exe 에 구워넣은 기본값 — 폴백)
    """
    candidates = [ROOT / name]
    bundle = _bundle_dir()
    if bundle is not None:
        candidates.append(bundle / name)
    return candidates


def _find_resource(name: str) -> Path | None:
    """후보 중 실제 존재하는 첫 경로를 반환(없으면 None)."""
    for path in _resource_candidates(name):
        if path.exists():
            return path
    return None


@dataclass
class Secrets:
    """.env 에서 읽는 비밀값."""

    gemini_api_key: str = ""
    anthropic_api_key: str = ""
    naver_datalab_client_id: str = ""
    naver_datalab_client_secret: str = ""
    image_api_provider: str = ""
    image_api_key: str = ""

    @property
    def has_gemini(self) -> bool:
        return bool(self.gemini_api_key)

    @property
    def has_anthropic(self) -> bool:
        return bool(self.anthropic_api_key)

    @property
    def has_datalab(self) -> bool:
        return bool(self.naver_datalab_client_id and self.naver_datalab_client_secret)

    @property
    def has_image_api(self) -> bool:
        return bool(self.image_api_provider and self.image_api_key)


@dataclass
class Config:
    """config.json + .env 를 합친 설정."""

    data: dict[str, Any] = field(default_factory=dict)
    secrets: Secrets = field(default_factory=Secrets)
    root: Path = ROOT

    def get(self, path: str, default: Any = None) -> Any:
        """점 경로로 중첩 값 접근. 예: config.get("content.model")."""
        node: Any = self.data
        for key in path.split("."):
            if not isinstance(node, dict) or key not in node:
                return default
            node = node[key]
        return node

    # 자주 쓰는 경로를 디렉터리(Path)로 반환 — 없으면 생성
    def media_output_dir(self) -> Path:
        d = self.root / self.get("images.output_dir", "generated_media")
        d.mkdir(parents=True, exist_ok=True)
        return d

    def user_photo_dir(self) -> Path:
        d = self.root / self.get("images.user_photo_dir", "user_photos")
        d.mkdir(parents=True, exist_ok=True)
        return d

    def assets_dir(self) -> Path:
        return self.root / self.get("automation.assets_dir", "assets")


def _load_config_file() -> dict[str, Any]:
    # exe/프로젝트 옆 → 번들(_MEIPASS) 순으로 config.json 탐색.
    cfg_path = _find_resource("config.json")
    if cfg_path is None:
        if (ROOT / "config.example.json").exists():
            raise FileNotFoundError(
                "config.json 이 없습니다. config.example.json 을 config.json 으로 복사한 뒤 "
                "값을 채워주세요."
            )
        return {}
    with cfg_path.open(encoding="utf-8") as f:
        return json.load(f)


def load_config() -> Config:
    """전역 설정을 로드한다."""
    # exe/프로젝트 옆 → 번들(_MEIPASS) 순으로 .env 탐색해 로드.
    env_path = _find_resource(".env")
    if env_path is not None:
        load_dotenv(env_path)
    secrets = Secrets(
        gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
        naver_datalab_client_id=os.getenv("NAVER_DATALAB_CLIENT_ID", ""),
        naver_datalab_client_secret=os.getenv("NAVER_DATALAB_CLIENT_SECRET", ""),
        image_api_provider=os.getenv("IMAGE_API_PROVIDER", ""),
        image_api_key=os.getenv("IMAGE_API_KEY", ""),
    )
    return Config(data=_load_config_file(), secrets=secrets)
