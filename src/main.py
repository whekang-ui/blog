"""CLI 엔트리포인트.

서브커맨드:
  topics   --auto [--count N] | --manual "주제" | --list
  generate --post-id ID | --all
  images   --post-id ID [--photos "0:2,1:5"]
  review   --post-id ID [--approve] [--force]
  publish  --post-id ID [--dry-run] [--public] [--schedule ISO] | --due [--dry-run]
  list     [--status STATUS]
  doctor   (환경/설정 점검)

전형적 흐름:
  python -m src.main topics --auto
  python -m src.main generate --all
  python -m src.main images --post-id 1
  python -m src.main review --post-id 1 --approve
  python -m src.main publish --post-id 1 --dry-run
"""

from __future__ import annotations

import argparse
import sys

from .config import Config, load_config
from .content.compliance import run_compliance
from .content.generator import extract_image_descriptions
from .images import prepare_media
from .images.user_photos import build_photo_map, list_user_photos
from .review import approve, render_preview
from .scheduler import TASK_SCHEDULER_GUIDE, process_due, publish_post
from .seo.optimizer import generate_optimized
from .storage.db import Database, open_db
from .topics.discovery import TopicCandidate, discover_topics
from .topics.manual import build_manual_topic


def _add_topic_to_db(db: Database, cand: TopicCandidate, source: str) -> int:
    return db.add_topic(
        cand.topic,
        keywords=[cand.primary_keyword, *cand.keywords],
        source=source,
        demand_score=cand.demand_score,
    )


def cmd_topics(config: Config, db: Database, args: argparse.Namespace) -> int:
    if args.list:
        posts = db.list_posts(status="topic")
        if not posts:
            print("대기 중인 주제가 없습니다.")
            return 0
        for p in posts:
            score = f"{p.demand_score:.1f}" if p.demand_score is not None else "-"
            print(f"#{p.id} [{p.source}] 수요 {score}  {p.topic}")
        return 0

    if args.manual:
        cand = build_manual_topic(config, args.manual, enrich=not args.no_enrich)
        pid = _add_topic_to_db(db, cand, "manual")
        print(f"수동 주제 추가: #{pid} {cand.topic} (키워드: {cand.primary_keyword})")
        return 0

    if args.auto:
        print("트렌드 주제를 발굴 중입니다(웹검색 + 데이터랩)...")
        cands = discover_topics(config, count=args.count)
        for c in cands:
            pid = _add_topic_to_db(db, c, "auto")
            print(f"  #{pid} 수요 {c.demand_score:.1f}  {c.topic}  [{c.primary_keyword}]")
        print(f"총 {len(cands)}개 주제를 큐에 추가했습니다.")
        return 0

    print("옵션을 지정하세요: --auto | --manual '주제' | --list")
    return 1


def _generate_one(config: Config, db: Database, post) -> None:
    cand = TopicCandidate(
        topic=post.topic,
        primary_keyword=(post.keywords[0] if post.keywords else post.topic),
        keywords=post.keywords or [post.topic],
        search_intent="정보형",
        rationale="",
        demand_score=post.demand_score or 50.0,
    )
    print(f"생성 중: #{post.id} {post.topic} ...")
    result = generate_optimized(config, cand)
    descriptions = result.post.image_descriptions()
    report = run_compliance(config, result.post.title, result.post.body, descriptions)
    db.update_post(
        post.id,
        status="draft",
        title=result.post.title,
        body=result.post.body,
        tags=result.post.tags,
        seo_score=result.report.score,
        seo_report=result.report.to_dict(),
        compliance=report.to_dict(),
    )
    print(
        f"  완료: SEO {result.report.score}점 (라운드 {result.rounds}), "
        f"컴플라이언스 경고 {len(report.warnings)}건, 글자수 {result.post.char_count}"
    )


def cmd_generate(config: Config, db: Database, args: argparse.Namespace) -> int:
    if args.all:
        posts = db.list_posts(status="topic")
    elif args.post_id:
        p = db.get_post(args.post_id)
        posts = [p] if p else []
    else:
        print("--post-id ID 또는 --all 을 지정하세요.")
        return 1
    if not posts:
        print("생성할 주제(status=topic)가 없습니다.")
        return 0
    for p in posts:
        _generate_one(config, db, p)
    return 0


def _parse_photo_map(spec: str | None) -> dict[int, int]:
    """'0:2,1:5' → {0:2, 1:5}."""
    result: dict[int, int] = {}
    if not spec:
        return result
    for pair in spec.split(","):
        if ":" in pair:
            a, b = pair.split(":", 1)
            try:
                result[int(a)] = int(b)
            except ValueError:
                continue
    return result


def cmd_images(config: Config, db: Database, args: argparse.Namespace) -> int:
    post = db.get_post(args.post_id)
    if not post or not post.body:
        print("본문이 있는 글(status=draft)이 아닙니다. 먼저 generate 하세요.")
        return 1
    descriptions = extract_image_descriptions(post.body)
    if not descriptions:
        print("본문에 [[IMAGE:...]] 자리표시자가 없습니다.")
        return 1

    photos = list_user_photos(config)
    photo_map = build_photo_map(photos, _parse_photo_map(args.photos))
    if args.list_photos:
        print(f"user_photos/ 사진 {len(photos)}개:")
        for i, p in enumerate(photos):
            print(f"  [{i}] {p.name}")
        print(f"본문 이미지 자리 {len(descriptions)}개:")
        for i, d in enumerate(descriptions):
            print(f"  [{i}] {d}")
        return 0

    prepared = prepare_media(config, descriptions, user_photo_map=photo_map)
    db.clear_media(post.id)
    for img in prepared:
        db.add_media(post.id, img.kind, img.path, img.alt_text, img.position)
    db.update_post(post.id, status="media_ready")
    print(f"이미지 {len(prepared)}개 준비 완료 (status=media_ready):")
    for img in prepared:
        print(f"  [{img.position}] ({img.kind}) {img.path}")
    return 0


def cmd_review(config: Config, db: Database, args: argparse.Namespace) -> int:
    post = db.get_post(args.post_id)
    if not post:
        print(f"#{args.post_id} 글을 찾을 수 없습니다.")
        return 1
    print(render_preview(db, post))
    if args.approve:
        ok, msg = approve(db, args.post_id, force=args.force)
        print(("✅ " if ok else "⚠️  ") + msg)
        return 0 if ok else 1
    return 0


def cmd_publish(config: Config, db: Database, args: argparse.Namespace) -> int:
    if args.due:
        logs = process_due(config, db, dry_run=args.dry_run)
        print("\n".join(logs))
        return 0
    if not args.post_id:
        print("--post-id ID 또는 --due 를 지정하세요.")
        return 1
    post = db.get_post(args.post_id)
    if not post:
        print(f"#{args.post_id} 글을 찾을 수 없습니다.")
        return 1
    if post.status != "approved" and not args.dry_run:
        print(f"승인된 글이 아닙니다 (현재: {post.status}). 먼저 review --approve 하세요.")
        return 1
    visibility = "public" if args.public else None
    plan = publish_post(
        config, db, post,
        dry_run=args.dry_run, visibility=visibility, scheduled_at=args.schedule,
    )
    print("\n".join(plan))
    if args.dry_run:
        print("\n(드라이런: 실제 입력은 하지 않았습니다.)")
    return 0


def cmd_list(config: Config, db: Database, args: argparse.Namespace) -> int:
    posts = db.list_posts(status=args.status)
    if not posts:
        print("글이 없습니다.")
        return 0
    for p in posts:
        seo = f"SEO {p.seo_score}" if p.seo_score is not None else ""
        print(f"#{p.id} [{p.status}] {p.title or p.topic}  {seo}")
    return 0


def cmd_doctor(config: Config, db: Database, args: argparse.Namespace) -> int:
    from .automation.humanize import gui_available
    from .automation.ui_locator import missing_assets

    provider = (config.get("content.provider", "gemini") or "gemini").lower()
    model = config.get("content.model", "")
    print("=== 환경 점검 ===")
    print(f"LLM 제공자: {provider} (model={model or '기본값'})")
    if provider == "gemini":
        ok = config.secrets.has_gemini
        print(f"  GEMINI_API_KEY: {'OK' if ok else '없음 → https://aistudio.google.com/apikey 무료발급'}")
    elif provider == "ollama":
        host = config.get("content.ollama_host", "http://localhost:11434")
        print(f"  Ollama 호스트: {host} (ollama 실행 + `ollama pull {model or 'qwen2.5:7b'}` 필요, 키 불필요)")
    elif provider == "anthropic":
        print(f"  ANTHROPIC_API_KEY: {'OK' if config.secrets.has_anthropic else '없음(유료)'}")
    print(f"네이버 데이터랩: {'OK' if config.secrets.has_datalab else '미설정(선택)'}")
    print(f"AI 이미지 API: {'OK' if config.secrets.has_image_api else '미설정(선택)'}")
    print(f"GUI 자동화 가능: {'예' if gui_available() else '아니오(헤드리스/미설치)'}")
    miss = missing_assets(config)
    if miss:
        print(f"누락된 버튼 캡처(assets/): {', '.join(miss)}")
    else:
        print("버튼 캡처(assets/): 모두 있음")
    print()
    print(TASK_SCHEDULER_GUIDE)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="naver-blog", description="네이버 블로그 자동화(피부과)")
    sub = p.add_subparsers(dest="command", required=True)

    t = sub.add_parser("topics", help="주제 발굴/입력")
    t.add_argument("--auto", action="store_true", help="트렌드 자동 발굴")
    t.add_argument("--manual", type=str, help="수동 주제 입력")
    t.add_argument("--no-enrich", action="store_true", help="수동 주제 키워드 자동보강 끔")
    t.add_argument("--count", type=int, default=8, help="자동 발굴 개수")
    t.add_argument("--list", action="store_true", help="대기 주제 목록")

    g = sub.add_parser("generate", help="콘텐츠 생성(+SEO+컴플라이언스)")
    g.add_argument("--post-id", type=int)
    g.add_argument("--all", action="store_true")

    im = sub.add_parser("images", help="이미지 준비")
    im.add_argument("--post-id", type=int, required=True)
    im.add_argument("--photos", type=str, help="본문자리:사진 매핑, 예 '0:2,1:5'")
    im.add_argument("--list-photos", action="store_true", help="사진/자리 목록만 보기")

    r = sub.add_parser("review", help="검토/승인")
    r.add_argument("--post-id", type=int, required=True)
    r.add_argument("--approve", action="store_true")
    r.add_argument("--force", action="store_true", help="high 경고 있어도 승인")

    pub = sub.add_parser("publish", help="발행/예약/드라이런")
    pub.add_argument("--post-id", type=int)
    pub.add_argument("--due", action="store_true", help="예약 도래분 일괄 발행")
    pub.add_argument("--dry-run", action="store_true")
    pub.add_argument("--public", action="store_true", help="공개로 발행(기본 비공개)")
    pub.add_argument("--schedule", type=str, help="예약 발행 시각 ISO (예: 2026-06-22T09:00)")

    ls = sub.add_parser("list", help="글 목록")
    ls.add_argument("--status", type=str)

    sub.add_parser("doctor", help="환경/설정 점검")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = load_config()
    db = open_db(config)

    handlers = {
        "topics": cmd_topics,
        "generate": cmd_generate,
        "images": cmd_images,
        "review": cmd_review,
        "publish": cmd_publish,
        "list": cmd_list,
        "doctor": cmd_doctor,
    }
    return handlers[args.command](config, db, args)


if __name__ == "__main__":
    sys.exit(main())
