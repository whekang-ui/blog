"""발행 전 의사 검토/승인.

글 미리보기 + SEO 점수 + 의료광고 컴플라이언스 경고를 한 화면에 보여주고, 사람이 승인하면
status 를 approved 로 올린다. high 등급 컴플라이언스 경고가 있으면 승인 시 경고한다.
"""

from __future__ import annotations

from .config import Config
from .storage.db import Database, Post


def render_preview(db: Database, post: Post) -> str:
    """글과 점검 결과를 사람이 읽기 좋은 텍스트로 정리."""
    lines: list[str] = []
    lines.append("=" * 70)
    lines.append(f"[#{post.id}] {post.title or '(제목 없음)'}")
    lines.append(f"상태: {post.status} | 주제: {post.topic}")
    if post.seo_score is not None:
        lines.append(f"SEO 점수: {post.seo_score}")
    lines.append("=" * 70)

    # 컴플라이언스 경고
    warnings = post.compliance.get("warnings", []) if post.compliance else []
    if warnings:
        lines.append("\n[의료광고 컴플라이언스 경고]")
        for w in warnings:
            mark = {"high": "■", "medium": "▲", "low": "·"}.get(w.get("severity"), "·")
            lines.append(f"  {mark} ({w.get('severity')}) {w.get('issue')}")
            if w.get("excerpt"):
                lines.append(f"      근거: {w['excerpt']}")
            if w.get("suggestion"):
                lines.append(f"      제안: {w['suggestion']}")
    else:
        lines.append("\n[의료광고 컴플라이언스] 경고 없음")

    # SEO 개선점
    checks = post.seo_report.get("checks", []) if post.seo_report else []
    failed = [c for c in checks if not c.get("passed")]
    if failed:
        lines.append("\n[SEO 개선점]")
        for c in failed:
            lines.append(f"  · {c.get('name')}: {c.get('detail')}")

    # 이미지
    media = db.list_media(post.id)
    if media:
        lines.append("\n[이미지]")
        for m in media:
            lines.append(f"  [{m.position}] ({m.kind}) {m.path}  alt='{m.alt_text}'")

    # 본문 미리보기
    lines.append("\n[본문]")
    lines.append((post.body or "").strip())
    lines.append("\n[태그] " + ", ".join(post.tags))
    lines.append("=" * 70)
    return "\n".join(lines)


def approve(db: Database, post_id: int, *, force: bool = False) -> tuple[bool, str]:
    """글을 승인(approved)한다.

    high 등급 컴플라이언스 경고가 있으면 force=False 일 때 거부한다.
    반환: (성공여부, 메시지)
    """
    post = db.get_post(post_id)
    if not post:
        return False, f"#{post_id} 글을 찾을 수 없습니다."
    if post.status not in ("draft", "media_ready"):
        return False, f"승인 가능한 상태가 아닙니다 (현재: {post.status})."

    warnings = post.compliance.get("warnings", []) if post.compliance else []
    high = [w for w in warnings if w.get("severity") == "high"]
    if high and not force:
        return (
            False,
            f"high 등급 의료광고 경고 {len(high)}건이 있습니다. 본문을 수정하거나 "
            "--force 로 승인하세요 (책임은 작성자에게 있음).",
        )

    db.update_post(post_id, status="approved")
    return True, f"#{post_id} 승인 완료 (status=approved)."
