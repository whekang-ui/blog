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
