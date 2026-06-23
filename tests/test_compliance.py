"""규칙 기반 의료광고 컴플라이언스 점검 테스트 (네트워크 불필요)."""

from src.content.compliance import check_image_descriptions, check_rules


def test_detects_banned_phrases():
    text = "이 시술은 완치를 보장하며 부작용이 전혀 없습니다. 국내 1위 효과!"
    warnings = check_rules(text)
    issues = " ".join(w.issue for w in warnings)
    assert any("완치" in w.issue or "단정" in w.issue for w in warnings)
    assert "부작용" in issues
    assert any(w.severity == "high" for w in warnings)


def test_clean_text_has_no_warnings():
    text = "여드름은 피지와 세균 등 여러 요인으로 생기며, 개인차가 있어 전문의 상담이 필요합니다."
    assert check_rules(text) == []


def test_blocks_ai_clinical_image_intent():
    descriptions = ["시술 전 환자 얼굴 사진", "스킨케어 개념 일러스트"]
    warnings = check_image_descriptions(descriptions)
    assert len(warnings) == 1
    assert warnings[0].severity == "high"


def test_allows_nonclinical_image():
    warnings = check_image_descriptions(["윤기나는 피부를 표현한 모델 이미지"])
    assert warnings == []
