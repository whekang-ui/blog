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


# ---- Gemini 이미지 ------------------------------------------------------
def test_gemini_image_success_monkeypatched(tmp_path, monkeypatch):
    cfg = _config(tmp_path, provider="gemini", key="g-test")
    png = b"\x89PNG\r\n gemini fake image"
    b64 = base64.b64encode(png).decode()

    def fake_call(model, key, body):
        assert key == "g-test"
        assert body["generationConfig"]["responseModalities"] == ["TEXT", "IMAGE"]
        return {"candidates": [{"content": {"parts": [
            {"text": "여기 이미지입니다"},
            {"inlineData": {"mimeType": "image/png", "data": b64}},
        ]}}]}

    monkeypatch.setattr(ai_image, "_gemini_generate_content", fake_call)
    out = ai_image.generate_ai_image(cfg, "윤기나는 피부 모델 컨셉", tmp_path / "g.png")
    assert out is not None
    assert (tmp_path / "g.png").read_bytes() == png


def test_gemini_image_clinical_blocked(tmp_path, monkeypatch):
    cfg = _config(tmp_path, provider="gemini", key="g-test")
    called = {"hit": False}

    def fake_call(model, key, body):
        called["hit"] = True
        return {}

    monkeypatch.setattr(ai_image, "_gemini_generate_content", fake_call)
    out = ai_image.generate_ai_image(cfg, "시술 전 환자 얼굴", tmp_path / "g.png")
    assert out is None
    assert called["hit"] is False  # 의료법 가드: API 호출 자체를 안 함


def test_gemini_image_no_image_in_response(tmp_path, monkeypatch):
    cfg = _config(tmp_path, provider="gemini", key="g-test")
    monkeypatch.setattr(
        ai_image, "_gemini_generate_content",
        lambda model, key, body: {"candidates": [{"content": {"parts": [{"text": "거부"}]}}]},
    )
    assert ai_image.generate_ai_image(cfg, "스킨케어 컨셉", tmp_path / "g.png") is None


# ---- Hugging Face 이미지 ------------------------------------------------
class _FakeResp:
    def __init__(self, status, *, content=b"", ctype="", json_data=None, text=""):
        self.status_code = status
        self.content = content
        self.headers = {"content-type": ctype}
        self._json = json_data
        self.text = text

    def json(self):
        if self._json is None:
            raise ValueError("no json")
        return self._json


def test_hf_image_success(tmp_path, monkeypatch):
    cfg = _config(tmp_path, provider="huggingface", key="hf_test")
    png = b"\x89PNG\r\n hf image bytes"

    def fake_post(endpoint, token, payload):
        assert token == "hf_test"
        assert "FLUX" in endpoint  # 기본 모델 경로
        assert payload["inputs"]
        return _FakeResp(200, content=png, ctype="image/png")

    monkeypatch.setattr(ai_image, "_hf_post", fake_post)
    path, reason = ai_image.generate_ai_image_verbose(
        cfg, "맑고 윤기나는 피부 모델", tmp_path / "hf.png"
    )
    assert reason is None
    assert path is not None
    assert (tmp_path / "hf.png").read_bytes() == png


def test_hf_image_loading_then_success(tmp_path, monkeypatch):
    cfg = _config(tmp_path, provider="hf", key="hf_test")
    png = b"\x89PNG ok"
    calls = {"n": 0}

    def fake_post(endpoint, token, payload):
        calls["n"] += 1
        if calls["n"] == 1:
            return _FakeResp(503, json_data={"estimated_time": 0.01})
        return _FakeResp(200, content=png, ctype="image/png")

    monkeypatch.setattr(ai_image, "_hf_post", fake_post)
    monkeypatch.setattr(ai_image.time, "sleep", lambda *_: None)
    path, reason = ai_image.generate_ai_image_verbose(cfg, "스킨케어 컷", tmp_path / "h.png")
    assert path is not None and reason is None
    assert calls["n"] == 2


def test_hf_image_error_returns_reason(tmp_path, monkeypatch):
    cfg = _config(tmp_path, provider="huggingface", key="hf_test")
    monkeypatch.setattr(
        ai_image, "_hf_post",
        lambda e, t, p: _FakeResp(404, json_data={"error": "model not found"}),
    )
    path, reason = ai_image.generate_ai_image_verbose(cfg, "스킨케어 컷", tmp_path / "h.png")
    assert path is None
    assert "404" in reason and "model not found" in reason


def test_hf_clinical_blocked_no_call(tmp_path, monkeypatch):
    cfg = _config(tmp_path, provider="huggingface", key="hf_test")
    called = {"hit": False}

    def fake_post(e, t, p):
        called["hit"] = True
        return _FakeResp(200, content=b"x", ctype="image/png")

    monkeypatch.setattr(ai_image, "_hf_post", fake_post)
    path, reason = ai_image.generate_ai_image_verbose(
        cfg, "시술 전 환자 얼굴", tmp_path / "h.png"
    )
    assert path is None
    assert "차단" in reason
    assert called["hit"] is False


def test_unknown_provider_reason(tmp_path):
    cfg = _config(tmp_path, provider="midjourney", key="x")
    path, reason = ai_image.generate_ai_image_verbose(cfg, "스킨케어", tmp_path / "x.png")
    assert path is None
    assert "미지원" in reason

