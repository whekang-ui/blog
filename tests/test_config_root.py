"""프로젝트 루트 경로 계산 테스트 (동결/비동결)."""

import sys
from pathlib import Path

from src import config


def test_root_when_not_frozen(monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)
    root = config._project_root()
    # 비동결: src/ 의 부모(저장소 루트)에 config.example.json 이 있어야 함
    assert (root / "config.example.json").exists()


def test_root_when_frozen(monkeypatch, tmp_path):
    fake_exe = tmp_path / "NaverBlogAutomation.exe"
    fake_exe.write_text("")  # 존재만 하면 됨
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(fake_exe), raising=False)
    # 동결: exe 가 놓인 폴더가 루트
    assert config._project_root() == tmp_path


def test_resource_prefers_exe_folder_then_bundle(monkeypatch, tmp_path):
    """exe 옆 파일이 우선, 없으면 번들(_MEIPASS) 파일 사용."""
    exe_dir = tmp_path / "app"
    bundle_dir = tmp_path / "bundle"
    exe_dir.mkdir()
    bundle_dir.mkdir()
    monkeypatch.setattr(config, "ROOT", exe_dir)
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle_dir), raising=False)

    # 둘 다 없으면 None
    assert config._find_resource("config.json") is None

    # 번들에만 있으면 번들 사용(폴백)
    (bundle_dir / "config.json").write_text("{}")
    assert config._find_resource("config.json") == bundle_dir / "config.json"

    # exe 옆에도 있으면 그게 우선
    (exe_dir / "config.json").write_text("{}")
    assert config._find_resource("config.json") == exe_dir / "config.json"


def test_load_config_reads_bundled_config(monkeypatch, tmp_path):
    """exe 옆엔 없고 번들에만 config.json 이 있을 때 그 내용을 로드."""
    exe_dir = tmp_path / "app"
    bundle_dir = tmp_path / "bundle"
    exe_dir.mkdir()
    bundle_dir.mkdir()
    (bundle_dir / "config.json").write_text(
        '{"content": {"provider": "gemini"}}', encoding="utf-8"
    )
    monkeypatch.setattr(config, "ROOT", exe_dir)
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle_dir), raising=False)
    cfg = config.load_config()
    assert cfg.get("content.provider") == "gemini"
