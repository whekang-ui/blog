"""데스크톱 GUI (Tkinter).

비개발자(피부과 의사)가 클릭만으로 전체 파이프라인을 쓸 수 있는 단일 창 앱.
모든 비즈니스 로직은 기존 모듈을 재사용한다(여기서는 UI + 스레드 처리만 담당).

실행: python -m src.gui
헤드리스(디스플레이 없는) 환경에서는 안내 메시지를 출력하고 종료한다.
"""

from __future__ import annotations

import queue
import threading
from typing import Callable

from .config import Config, load_config
from .content.compliance import run_compliance
from .content.generator import extract_image_descriptions
from .images import prepare_media
from .images.user_photos import build_photo_map, list_user_photos
from .review import approve, render_preview
from .scheduler import publish_post
from .seo.optimizer import generate_optimized
from .storage.db import Database, open_db
from .topics.discovery import TopicCandidate, discover_topics
from .topics.manual import build_manual_topic


def _topic_from_post(post) -> TopicCandidate:
    return TopicCandidate(
        topic=post.topic,
        primary_keyword=(post.keywords[0] if post.keywords else post.topic),
        keywords=post.keywords or [post.topic],
        search_intent="정보형",
        rationale="",
        demand_score=post.demand_score or 50.0,
    )


def _parse_photo_map(spec: str) -> dict[int, int]:
    result: dict[int, int] = {}
    for pair in (spec or "").split(","):
        if ":" in pair:
            a, b = pair.split(":", 1)
            try:
                result[int(a)] = int(b)
            except ValueError:
                continue
    return result


class App:
    def __init__(self, root, config: Config, db: Database) -> None:
        import tkinter as tk
        from tkinter import ttk

        self.tk = tk
        self.ttk = ttk
        self.root = root
        self.config = config
        self.db = db
        self._log_queue: "queue.Queue[str]" = queue.Queue()

        root.title("네이버 블로그 자동화 (피부과)")
        root.geometry("960x720")

        self._build_post_list()
        self._build_tabs()
        self._build_log()

        self.refresh_posts()
        self.root.after(150, self._drain_log)

    # ---- layout ---------------------------------------------------------
    def _build_post_list(self) -> None:
        tk, ttk = self.tk, self.ttk
        frame = ttk.LabelFrame(self.root, text="글 목록")
        frame.pack(fill="x", padx=8, pady=6)
        self.tree = ttk.Treeview(
            frame, columns=("status", "seo", "title"), show="headings", height=6
        )
        for col, label, w in (
            ("status", "상태", 100), ("seo", "SEO", 60), ("title", "제목/주제", 700)
        ):
            self.tree.heading(col, text=label)
            self.tree.column(col, width=w, anchor="w")
        self.tree.pack(side="left", fill="x", expand=True, padx=4, pady=4)
        ttk.Button(frame, text="새로고침", command=self.refresh_posts).pack(
            side="right", padx=4
        )

    def _build_tabs(self) -> None:
        tk, ttk = self.tk, self.ttk
        nb = ttk.Notebook(self.root)
        nb.pack(fill="both", expand=True, padx=8, pady=4)

        # 1) 주제
        t1 = ttk.Frame(nb)
        nb.add(t1, text="1. 주제")
        ttk.Label(t1, text="자동 발굴 개수:").grid(row=0, column=0, sticky="w", padx=6, pady=6)
        self.count_var = tk.IntVar(value=8)
        ttk.Spinbox(t1, from_=1, to=20, textvariable=self.count_var, width=5).grid(
            row=0, column=1, sticky="w"
        )
        ttk.Button(t1, text="트렌드 자동 발굴", command=self.on_auto_topics).grid(
            row=0, column=2, padx=6
        )
        ttk.Label(t1, text="수동 주제:").grid(row=1, column=0, sticky="w", padx=6, pady=6)
        self.manual_var = tk.StringVar()
        ttk.Entry(t1, textvariable=self.manual_var, width=50).grid(
            row=1, column=1, columnspan=2, sticky="w"
        )
        ttk.Button(t1, text="수동 추가", command=self.on_manual_topic).grid(
            row=1, column=3, padx=6
        )

        # 2) 생성
        t2 = ttk.Frame(nb)
        nb.add(t2, text="2. 생성")
        ttk.Label(
            t2, text="목록에서 글을 선택한 뒤 생성하세요 (SEO 최적화 + 의료광고 점검)."
        ).pack(anchor="w", padx=6, pady=6)
        ttk.Button(t2, text="선택 글 생성", command=self.on_generate).pack(
            anchor="w", padx=6
        )

        # 3) 이미지
        t3 = ttk.Frame(nb)
        nb.add(t3, text="3. 이미지")
        ttk.Button(t3, text="이미지 자리/내 사진 보기", command=self.on_list_photos).grid(
            row=0, column=0, padx=6, pady=6, sticky="w"
        )
        ttk.Label(t3, text="매핑(본문자리:사진번호, 예 0:2,1:5):").grid(
            row=1, column=0, sticky="w", padx=6
        )
        self.photo_map_var = tk.StringVar()
        ttk.Entry(t3, textvariable=self.photo_map_var, width=40).grid(
            row=1, column=1, sticky="w"
        )
        ttk.Button(t3, text="이미지 준비", command=self.on_prepare_images).grid(
            row=1, column=2, padx=6
        )

        # 4) 검토·발행
        t4 = ttk.Frame(nb)
        nb.add(t4, text="4. 검토·발행")
        ttk.Button(t4, text="미리보기", command=self.on_preview).grid(
            row=0, column=0, padx=6, pady=6, sticky="w"
        )
        ttk.Button(t4, text="승인", command=self.on_approve).grid(
            row=0, column=1, padx=6, sticky="w"
        )
        self.public_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(t4, text="공개로 발행(기본 비공개)", variable=self.public_var).grid(
            row=1, column=0, columnspan=2, sticky="w", padx=6
        )
        ttk.Label(t4, text="예약시각(ISO, 예 2026-06-22T09:00):").grid(
            row=2, column=0, sticky="w", padx=6
        )
        self.schedule_var = tk.StringVar()
        ttk.Entry(t4, textvariable=self.schedule_var, width=30).grid(
            row=2, column=1, sticky="w"
        )
        ttk.Button(t4, text="드라이런(계획만)", command=lambda: self.on_publish(True)).grid(
            row=3, column=0, padx=6, pady=6, sticky="w"
        )
        ttk.Button(t4, text="발행", command=lambda: self.on_publish(False)).grid(
            row=3, column=1, padx=6, sticky="w"
        )

    def _build_log(self) -> None:
        ttk = self.ttk
        frame = ttk.LabelFrame(self.root, text="로그")
        frame.pack(fill="both", expand=True, padx=8, pady=6)
        self.log = self.tk.Text(frame, height=12, wrap="word", state="disabled")
        self.log.pack(fill="both", expand=True, padx=4, pady=4)

    # ---- helpers --------------------------------------------------------
    def log_msg(self, msg: str) -> None:
        self._log_queue.put(msg)

    def _drain_log(self) -> None:
        while not self._log_queue.empty():
            msg = self._log_queue.get_nowait()
            self.log.configure(state="normal")
            self.log.insert("end", msg + "\n")
            self.log.see("end")
            self.log.configure(state="disabled")
        self.root.after(150, self._drain_log)

    def selected_post_id(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            self.log_msg("⚠️ 글 목록에서 글을 먼저 선택하세요.")
            return None
        return int(sel[0])

    def refresh_posts(self) -> None:
        for row in self.tree.get_children():
            self.tree.delete(row)
        for p in self.db.list_posts():
            seo = f"{p.seo_score}" if p.seo_score is not None else ""
            self.tree.insert("", "end", iid=str(p.id),
                             values=(p.status, seo, p.title or p.topic))

    def run_async(self, label: str, fn: Callable[[], None]) -> None:
        """장기 작업을 스레드로 실행. 완료 시 목록 새로고침."""
        self.log_msg(f"▶ {label} 시작...")

        def worker() -> None:
            try:
                fn()
                self.log_msg(f"✅ {label} 완료")
            except Exception as exc:  # noqa: BLE001
                self.log_msg(f"❌ {label} 실패: {exc}")
            finally:
                self.root.after(0, self.refresh_posts)

        threading.Thread(target=worker, daemon=True).start()

    # ---- actions --------------------------------------------------------
    def on_auto_topics(self) -> None:
        count = self.count_var.get()

        def task() -> None:
            cands = discover_topics(self.config, count=count)
            for c in cands:
                pid = self.db.add_topic(
                    c.topic, keywords=[c.primary_keyword, *c.keywords],
                    source="auto", demand_score=c.demand_score,
                )
                self.log_msg(f"  #{pid} 수요 {c.demand_score:.1f}  {c.topic}")

        self.run_async("트렌드 주제 발굴", task)

    def on_manual_topic(self) -> None:
        topic = self.manual_var.get().strip()
        if not topic:
            self.log_msg("⚠️ 수동 주제를 입력하세요.")
            return

        def task() -> None:
            cand = build_manual_topic(self.config, topic)
            pid = self.db.add_topic(
                cand.topic, keywords=[cand.primary_keyword, *cand.keywords],
                source="manual", demand_score=cand.demand_score,
            )
            self.log_msg(f"  수동 주제 추가 #{pid}: {cand.topic}")

        self.run_async("수동 주제 추가", task)

    def on_generate(self) -> None:
        pid = self.selected_post_id()
        if pid is None:
            return
        post = self.db.get_post(pid)
        if not post:
            return

        def task() -> None:
            result = generate_optimized(self.config, _topic_from_post(post))
            descs = result.post.image_descriptions()
            report = run_compliance(
                self.config, result.post.title, result.post.body, descs
            )
            self.db.update_post(
                pid, status="draft", title=result.post.title, body=result.post.body,
                tags=result.post.tags, seo_score=result.report.score,
                seo_report=result.report.to_dict(), compliance=report.to_dict(),
            )
            self.log_msg(
                f"  SEO {result.report.score}점, 컴플라이언스 경고 {len(report.warnings)}건"
            )

        self.run_async(f"#{pid} 콘텐츠 생성", task)

    def on_list_photos(self) -> None:
        pid = self.selected_post_id()
        if pid is None:
            return
        post = self.db.get_post(pid)
        if not post or not post.body:
            self.log_msg("⚠️ 생성된 본문이 없습니다. 먼저 생성하세요.")
            return
        descs = extract_image_descriptions(post.body)
        photos = list_user_photos(self.config)
        self.log_msg(f"본문 이미지 자리 {len(descs)}개:")
        for i, d in enumerate(descs):
            self.log_msg(f"  [{i}] {d}")
        self.log_msg(f"내 사진(user_photos/) {len(photos)}개:")
        for i, p in enumerate(photos):
            self.log_msg(f"  [{i}] {p.name}")

    def on_prepare_images(self) -> None:
        pid = self.selected_post_id()
        if pid is None:
            return
        post = self.db.get_post(pid)
        if not post or not post.body:
            self.log_msg("⚠️ 생성된 본문이 없습니다.")
            return
        spec = self.photo_map_var.get()

        def task() -> None:
            descs = extract_image_descriptions(post.body)
            photos = list_user_photos(self.config)
            photo_map = build_photo_map(photos, _parse_photo_map(spec))
            prepared = prepare_media(
                self.config, descs, user_photo_map=photo_map, log=self.log_msg
            )
            self.db.clear_media(pid)
            for img in prepared:
                self.db.add_media(pid, img.kind, img.path, img.alt_text, img.position)
            self.db.update_post(pid, status="media_ready")
            for img in prepared:
                self.log_msg(f"  [{img.position}] ({img.kind}) {img.path}")

        self.run_async(f"#{pid} 이미지 준비", task)

    def on_preview(self) -> None:
        pid = self.selected_post_id()
        if pid is None:
            return
        post = self.db.get_post(pid)
        if not post:
            return
        self.log_msg(render_preview(self.db, post))

    def on_approve(self) -> None:
        pid = self.selected_post_id()
        if pid is None:
            return
        post = self.db.get_post(pid)
        force = False
        warnings = (post.compliance or {}).get("warnings", []) if post else []
        if any(w.get("severity") == "high" for w in warnings):
            from tkinter import messagebox
            force = messagebox.askyesno(
                "의료광고 경고",
                "high 등급 의료광고 경고가 있습니다. 그래도 승인하시겠습니까?\n"
                "(책임은 작성자에게 있습니다)",
            )
            if not force:
                self.log_msg("승인 취소됨. 본문을 수정하세요.")
                return
        ok, msg = approve(self.db, pid, force=force)
        self.log_msg(("✅ " if ok else "⚠️ ") + msg)
        self.refresh_posts()

    def on_publish(self, dry_run: bool) -> None:
        pid = self.selected_post_id()
        if pid is None:
            return
        post = self.db.get_post(pid)
        if not post:
            return
        if post.status != "approved" and not dry_run:
            self.log_msg("⚠️ 승인된 글이 아닙니다. 먼저 승인하세요.")
            return
        visibility = "public" if self.public_var.get() else None
        schedule = self.schedule_var.get().strip() or None

        def task() -> None:
            plan = publish_post(
                self.config, self.db, post, dry_run=dry_run,
                visibility=visibility, scheduled_at=schedule,
            )
            for line in plan:
                self.log_msg("  " + line)
            if dry_run:
                self.log_msg("  (드라이런: 실제 입력 안 함)")

        self.run_async(f"#{pid} {'드라이런' if dry_run else '발행'}", task)


def main() -> int:
    try:
        import tkinter as tk
    except Exception as exc:  # noqa: BLE001
        print(f"Tkinter 를 사용할 수 없습니다: {exc}")
        return 1
    try:
        root = tk.Tk()
    except Exception as exc:  # noqa: BLE001 - 헤드리스 환경
        print(
            "GUI 를 띄울 수 없습니다(디스플레이 없음). Windows 데스크톱에서 실행하세요.\n"
            f"원인: {exc}"
        )
        return 1
    config = load_config()
    db = open_db(config)
    App(root, config, db)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
