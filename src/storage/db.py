"""SQLite 저장소.

파이프라인 상태를 글(post) 한 행으로 추적한다. status 흐름:
    topic -> draft -> media_ready -> approved -> published
이미지는 media 테이블에 post_id 로 연결.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

SCHEMA = """
CREATE TABLE IF NOT EXISTS posts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    topic         TEXT NOT NULL,
    keywords      TEXT,                       -- JSON list
    status        TEXT NOT NULL DEFAULT 'topic',
    source        TEXT,                       -- 'auto' | 'manual'
    demand_score  REAL,                       -- 트렌드/검색량 기반 점수
    title         TEXT,
    body          TEXT,                       -- 본문(이미지 자리표시자 포함)
    tags          TEXT,                       -- JSON list
    seo_score     REAL,
    seo_report    TEXT,                       -- JSON
    compliance    TEXT,                       -- JSON (경고 목록)
    scheduled_at  TEXT,                       -- 예약 발행 시각 (ISO)
    published_at  TEXT,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS media (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id   INTEGER NOT NULL,
    kind      TEXT NOT NULL,                  -- 'ai' | 'infographic' | 'user'
    path      TEXT NOT NULL,
    alt_text  TEXT,
    position  INTEGER NOT NULL DEFAULT 0,     -- 본문 내 삽입 순서
    FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE
);
"""


@dataclass
class Post:
    id: int
    topic: str
    keywords: list[str]
    status: str
    source: str | None
    demand_score: float | None
    title: str | None
    body: str | None
    tags: list[str]
    seo_score: float | None
    seo_report: dict[str, Any]
    compliance: dict[str, Any]
    scheduled_at: str | None
    published_at: str | None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Post":
        return cls(
            id=row["id"],
            topic=row["topic"],
            keywords=json.loads(row["keywords"] or "[]"),
            status=row["status"],
            source=row["source"],
            demand_score=row["demand_score"],
            title=row["title"],
            body=row["body"],
            tags=json.loads(row["tags"] or "[]"),
            seo_score=row["seo_score"],
            seo_report=json.loads(row["seo_report"] or "{}"),
            compliance=json.loads(row["compliance"] or "{}"),
            scheduled_at=row["scheduled_at"],
            published_at=row["published_at"],
        )


@dataclass
class Media:
    id: int
    post_id: int
    kind: str
    path: str
    alt_text: str | None
    position: int

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Media":
        return cls(
            id=row["id"],
            post_id=row["post_id"],
            kind=row["kind"],
            path=row["path"],
            alt_text=row["alt_text"],
            position=row["position"],
        )


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class Database:
    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        self._init_schema()

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._conn() as conn:
            conn.executescript(SCHEMA)

    # ---- posts ----------------------------------------------------------
    def add_topic(
        self,
        topic: str,
        *,
        keywords: list[str] | None = None,
        source: str = "manual",
        demand_score: float | None = None,
    ) -> int:
        now = _now()
        with self._conn() as conn:
            cur = conn.execute(
                """INSERT INTO posts (topic, keywords, status, source, demand_score,
                                      created_at, updated_at)
                   VALUES (?, ?, 'topic', ?, ?, ?, ?)""",
                (topic, json.dumps(keywords or [], ensure_ascii=False), source,
                 demand_score, now, now),
            )
            return int(cur.lastrowid)

    def update_post(self, post_id: int, **fields: Any) -> None:
        if not fields:
            return
        # dict/list 값은 JSON 직렬화
        cleaned: dict[str, Any] = {}
        for key, value in fields.items():
            if isinstance(value, (dict, list)):
                cleaned[key] = json.dumps(value, ensure_ascii=False)
            else:
                cleaned[key] = value
        cleaned["updated_at"] = _now()
        assignments = ", ".join(f"{k} = ?" for k in cleaned)
        with self._conn() as conn:
            conn.execute(
                f"UPDATE posts SET {assignments} WHERE id = ?",
                (*cleaned.values(), post_id),
            )

    def get_post(self, post_id: int) -> Post | None:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
            return Post.from_row(row) if row else None

    def list_posts(self, status: str | None = None) -> list[Post]:
        query = "SELECT * FROM posts"
        params: tuple[Any, ...] = ()
        if status:
            query += " WHERE status = ?"
            params = (status,)
        query += " ORDER BY COALESCE(demand_score, 0) DESC, id DESC"
        with self._conn() as conn:
            return [Post.from_row(r) for r in conn.execute(query, params).fetchall()]

    def count_published_today(self) -> int:
        today = datetime.now().date().isoformat()
        with self._conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM posts "
                "WHERE status = 'published' AND substr(published_at, 1, 10) = ?",
                (today,),
            ).fetchone()
            return int(row["c"])

    # ---- media ----------------------------------------------------------
    def add_media(
        self, post_id: int, kind: str, path: str, alt_text: str | None, position: int
    ) -> int:
        with self._conn() as conn:
            cur = conn.execute(
                """INSERT INTO media (post_id, kind, path, alt_text, position)
                   VALUES (?, ?, ?, ?, ?)""",
                (post_id, kind, path, alt_text, position),
            )
            return int(cur.lastrowid)

    def list_media(self, post_id: int) -> list[Media]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM media WHERE post_id = ? ORDER BY position ASC",
                (post_id,),
            ).fetchall()
            return [Media.from_row(r) for r in rows]

    def clear_media(self, post_id: int) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM media WHERE post_id = ?", (post_id,))


def open_db(config: Any) -> Database:
    """설정 루트에 blog.db 를 연다."""
    return Database(Path(config.root) / "blog.db")
