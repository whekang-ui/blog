"""SEO 점수 산출 테스트 (네트워크 불필요)."""

from src.content.generator import GeneratedPost
from src.seo.scorer import score_post
from src.topics.discovery import TopicCandidate


def _topic() -> TopicCandidate:
    return TopicCandidate(
        topic="여드름 흉터 치료",
        primary_keyword="여드름 흉터",
        keywords=["여드름 흉터", "흉터 레이저"],
        search_intent="정보형",
        rationale="",
        demand_score=70.0,
    )


def _good_body() -> str:
    # 키워드를 과반복하지 않는 자연스러운 본문 (단락도 짧게)
    para = (
        "피부에 생기는 흔한 고민 중 하나입니다.\n"
        "발생 원인은 사람마다 다르고 여러 요인이 함께 작용합니다.\n"
        "생활 습관과 피부 상태에 따라 진행 양상도 달라집니다.\n"
        "정확한 평가가 먼저 이루어져야 합니다.\n"
    ) * 6
    return (
        "## 여드름 흉터란\n여드름 흉터의 형성 과정을 알아봅니다.\n" + para
        + "[[IMAGE:흉터 종류 인포그래픽]]\n"
        "## 치료 방법\n치료 방법은 다양합니다.\n" + para
        + "[[IMAGE:치료 과정 정보]]\n"
        "## 주의사항\n관리 시 주의할 점입니다.\n" + para
        + "[[IMAGE:스킨케어 개념 이미지]]\n"
        "## 요약\n정확한 진단과 치료는 전문의 상담이 필요합니다."
    )


def test_high_quality_post_scores_well():
    post = GeneratedPost(
        title="여드름 흉터 치료, 꼭 알아야 할 점",
        body=_good_body(),
        tags=["여드름흉터", "피부과", "흉터치료", "레이저", "스킨케어",
              "여드름", "피부관리", "흉터", "트러블", "피부고민"],
    )
    report = score_post(post, _topic())
    assert report.score >= 80


def test_short_post_flags_length_and_images():
    post = GeneratedPost(title="여드름 흉터", body="짧은 글입니다.", tags=["여드름"])
    report = score_post(post, _topic())
    assert report.score < 60
    names = [c.name for c in report.checks if not c.passed]
    assert "본문 분량" in names
    assert "이미지" in names
