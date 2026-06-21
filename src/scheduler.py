"""발행 스케줄링.

승인된(approved) 글을 발행한다. 두 가지 방식:
1) 네이버 네이티브 예약발행: scheduled_at 을 에디터에 넣어 네이버가 시각에 맞춰 발행 → PC 가
   항상 켜져 있을 필요 없음(권장).
2) 로컬 스케줄: Windows 작업 스케줄러가 주기적으로 `main.py publish --due` 를 실행해, 예약시각이
   지난 글을 발행.

하루 발행 수 상한(max_posts_per_day)을 지킨다.
"""

from __future__ import annotations

from datetime import datetime

from .automation.naver_editor import NaverEditor, PublishOptions
from .config import Config
from .images import PreparedImage
from .storage.db import Database, Post


def _post_images(db: Database, post: Post) -> list[PreparedImage]:
    media = db.list_media(post.id)
    return [
        PreparedImage(
            description=m.alt_text or "",
            path=m.path,
            kind=m.kind,
            alt_text=m.alt_text or "",
            position=m.position,
        )
        for m in media
    ]


def publish_post(
    config: Config,
    db: Database,
    post: Post,
    *,
    dry_run: bool = False,
    visibility: str | None = None,
    scheduled_at: str | None = None,
) -> list[str]:
    """단일 글 발행. 동작 로그(또는 dry-run 계획)를 반환."""
    editor = NaverEditor(config)
    options = PublishOptions(
        visibility=visibility or config.get("publishing.default_visibility", "private"),
        scheduled_at=scheduled_at or post.scheduled_at,
        dry_run=dry_run,
    )
    plan = editor.publish(
        title=post.title or post.topic,
        body=post.body or "",
        tags=post.tags,
        images=_post_images(db, post),
        options=options,
    )
    if not dry_run:
        db.update_post(
            post.id,
            status="published",
            published_at=datetime.now().isoformat(timespec="seconds"),
        )
    return plan


def process_due(config: Config, db: Database, *, dry_run: bool = False) -> list[str]:
    """예약시각이 지난 approved 글을 하루 상한 내에서 발행한다."""
    max_per_day = config.get("publishing.max_posts_per_day", 2)
    logs: list[str] = []
    published_today = db.count_published_today()

    now = datetime.now()
    for post in db.list_posts(status="approved"):
        if published_today >= max_per_day:
            logs.append(f"하루 발행 상한({max_per_day}) 도달 — 나머지는 다음 실행으로 미룸.")
            break
        # 예약시각이 없거나(즉시 대상), 지났으면 발행
        if post.scheduled_at:
            try:
                if datetime.fromisoformat(post.scheduled_at) > now:
                    continue
            except ValueError:
                pass
        logs.append(f"--- 발행: #{post.id} {post.title}")
        logs.extend(publish_post(config, db, post, dry_run=dry_run))
        if not dry_run:
            published_today += 1
    if not logs:
        logs.append("발행할 글이 없습니다 (approved + 예약시각 도래 글 없음).")
    return logs


TASK_SCHEDULER_GUIDE = """
[Windows 작업 스케줄러 등록 방법]
1) 작업 스케줄러 열기 → '기본 작업 만들기'.
2) 트리거: 매일 원하는 시각 (예: 오전 9시).
3) 동작: 프로그램 시작
   - 프로그램/스크립트: python
   - 인수 추가: -m src.main publish --due
   - 시작 위치: 이 프로젝트 폴더 경로
4) (권장) 네이버 네이티브 예약발행을 쓰면, 발행 시 scheduled_at 을 에디터에 넣어 네이버가
   대신 시각에 맞춰 공개하므로 PC 가 항상 켜져 있지 않아도 됩니다.
""".strip()
