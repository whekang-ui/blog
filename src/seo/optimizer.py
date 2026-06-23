"""SEO 최적화 루프.

글을 생성 → 점수화 → 목표 미달이면 실패 항목을 피드백으로 재생성. 설정된 라운드 수만큼 반복하고
가장 높은 점수의 글을 반환한다.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..config import Config
from ..content.generator import GeneratedPost, generate_post
from ..topics.discovery import TopicCandidate
from .scorer import SeoReport, score_post


@dataclass
class OptimizedResult:
    post: GeneratedPost
    report: SeoReport
    rounds: int


def generate_optimized(config: Config, topic: TopicCandidate) -> OptimizedResult:
    """SEO 목표 점수를 만족할 때까지(또는 최대 라운드까지) 생성·개선한다."""
    min_score = config.get("seo.min_score", 80)
    max_rounds = config.get("seo.max_regeneration_rounds", 2)
    min_chars = config.get("content.min_chars", 1500)
    min_images = config.get("images.min_images_per_post", 3)

    best: OptimizedResult | None = None
    feedback: str | None = None

    for round_idx in range(max_rounds + 1):
        post = generate_post(config, topic, feedback=feedback)
        report = score_post(post, topic, min_chars=min_chars, min_images=min_images)
        current = OptimizedResult(post=post, report=report, rounds=round_idx + 1)

        if best is None or report.score > best.report.score:
            best = current

        if report.score >= min_score:
            break

        # 다음 라운드 피드백 = 실패 항목 개선 제안 모음
        suggestions = report.failed_suggestions
        if not suggestions:
            break
        feedback = "다음 SEO 개선점을 반영하라:\n- " + "\n- ".join(suggestions)

    assert best is not None
    return best
