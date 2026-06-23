"""예약발행 포맷/계획 테스트 (GUI/네트워크 불필요)."""

from src.automation.naver_editor import NaverEditor, PublishOptions, format_schedule
from src.config import Config, Secrets


def _config(tmp_path) -> Config:
    return Config(
        data={
            "automation": {
                "schedule_date_format": "%Y.%m.%d",
                "schedule_time_format": "%H:%M",
            }
        },
        secrets=Secrets(),
        root=tmp_path,
    )


def test_format_schedule_parses_iso():
    assert format_schedule("2026-06-22T09:00", "%Y.%m.%d", "%H:%M") == (
        "2026.06.22", "09:00"
    )


def test_format_schedule_bad_input():
    assert format_schedule("not-a-date", "%Y.%m.%d", "%H:%M") is None


def test_dry_run_plan_includes_schedule_steps(tmp_path):
    editor = NaverEditor(_config(tmp_path))
    plan = editor.publish(
        title="여드름 흉터 치료",
        body="## 개요\n본문입니다.",
        tags=["여드름흉터"],
        images=[],
        options=PublishOptions(
            visibility="private", scheduled_at="2026-06-22T09:00", dry_run=True
        ),
    )
    text = "\n".join(plan)
    assert "예약 토글 ON" in text
    assert "2026.06.22" in text
    assert "09:00" in text


def test_dry_run_plan_immediate_publish(tmp_path):
    editor = NaverEditor(_config(tmp_path))
    plan = editor.publish(
        title="제목", body="본문", tags=[], images=[],
        options=PublishOptions(visibility="public", dry_run=True),
    )
    assert any("즉시 발행(공개)" in line for line in plan)
