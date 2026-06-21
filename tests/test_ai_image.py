"""AI 비임상 이미지 생성 테스트 (네트워크 없이 monkeypatch)."""

import base64

from src.config import Config, Secrets
from src.images import ai_image


def _config(tmp_path, *, provider="", key="") -> Config:
    return Config(
        data={"images": {"ai_size": "1024x1024"}},
        secrets=Secrets(image_api_provider=provider, image_api_key=key),
        root=tmp_path,
    )


def test_is_clinical_intent_blocks_patient_and_beforeafter():
    assert ai_image.is_clinical_intent("시술 전 환자 얼굴")
    assert ai_image.is_clinical_intent("before and after photo")
    assert not ai_image.is_clinical_intent("윤기나는 피부 모델 컨셉")


def test_build_prompt_includes_safe_style():
    prompt = ai_image.build_prompt("스킨케어 모델")
    assert "non-clinical" in prompt
    assert "스킨케어 모델" in prompt


def test_disabled_without_api_key(tmp_path):
    cfg = _config(tmp_path)  # 키 없음 → 비활성
    assert ai_image.generate_ai_image(cfg, "스킨케어 모델", tmp_path / "x.png") is None


def test_clinical_intent_refused_even_with_key(tmp_path):
    cfg = _config(tmp_path, provider="openai", key="sk-test")
    out = ai_image.generate_ai_image(cfg, "시술 전 환자 사진", tmp_path / "x.png")
    assert out is None  # 의료법 가드


def test_openai_success_path_monkeypatched(tmp_path, monkeypatch):
    cfg = _config(tmp_path, provider="openai", key="sk-test")
    png_bytes = b"\x89PNG\r\n fake image bytes"
    b64 = base64.b64encode(png_bytes).decode()

    class _Img:
        b64_json = b64

    class _Result:
        data = [_Img()]

    class _Images:
        def generate(self, **kwargs):
            assert kwargs["size"] == "1024x1024"
            return _Result()

    class _FakeClient:
        images = _Images()

    monkeypatch.setattr(ai_image, "_build_openai_client", lambda key: _FakeClient())
    out = ai_image.generate_ai_image(cfg, "윤기나는 피부 컨셉", tmp_path / "ai.png")
    assert out is not None
    assert (tmp_path / "ai.png").read_bytes() == png_bytes


def test_openai_failure_returns_none(tmp_path, monkeypatch):
    cfg = _config(tmp_path, provider="openai", key="sk-test")

    def _boom(key):
        raise RuntimeError("network down")

    monkeypatch.setattr(ai_image, "_build_openai_client", _boom)
    assert ai_image.generate_ai_image(cfg, "스킨케어 컨셉", tmp_path / "x.png") is None
