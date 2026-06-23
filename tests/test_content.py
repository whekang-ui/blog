"""본문 파싱/세그먼트 분해 테스트 (네트워크/GUI 불필요)."""

from src.automation.naver_editor import build_segments
from src.content.generator import GeneratedPost, extract_image_descriptions
from src.images import PreparedImage


def test_extract_image_descriptions():
    body = "앞 [[IMAGE:첫 이미지]] 중간 [[IMAGE:둘째 이미지]] 끝"
    descs = extract_image_descriptions(body)
    assert descs == ["첫 이미지", "둘째 이미지"]


def test_char_count_excludes_image_tokens():
    post = GeneratedPost(title="t", body="가나다 [[IMAGE:x]] 라마바", tags=[])
    # 이미지 토큰을 제외한 글자 수 (공백 포함)
    assert post.char_count == len("가나다  라마바")


def test_build_segments_interleaves_images_in_order():
    body = "도입 문단\n[[IMAGE:a]]\n본문 문단\n[[IMAGE:b]]\n마무리"
    images = [
        PreparedImage("a", "/img/a.png", "infographic", "alt a", 0),
        PreparedImage("b", "/img/b.png", "user", "alt b", 1),
    ]
    segments = build_segments(body, images)
    kinds = [s.kind for s in segments]
    assert kinds == ["text", "image", "text", "image", "text"]
    assert segments[1].image.path == "/img/a.png"
    assert segments[3].image.path == "/img/b.png"


def test_build_segments_without_images():
    segments = build_segments("이미지 없는 본문", [])
    assert len(segments) == 1
    assert segments[0].kind == "text"
