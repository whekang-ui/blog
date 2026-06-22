"""LLM 제공자 라우팅/파싱 테스트 (네트워크 없이)."""

import pytest

from src.config import Config, Secrets
from src.llm import LLM, LLMError, _parse_json


def _cfg(tmp_path, provider, model=None, gemini_key="", anthropic_key=""):
    data = {"content": {"provider": provider}}
    if model:
        data["content"]["model"] = model
    return Config(
        data=data,
        secrets=Secrets(gemini_api_key=gemini_key, anthropic_api_key=anthropic_key),
        root=tmp_path,
    )


def test_default_provider_is_gemini(tmp_path):
    llm = LLM(_cfg(tmp_path, "gemini", gemini_key="k"))
    assert llm.provider == "gemini"
    assert llm.model == "gemini-2.0-flash"


def test_ollama_default_model(tmp_path):
    llm = LLM(_cfg(tmp_path, "ollama"))
    assert llm.model == "qwen2.5:7b"  # 키 불필요


def test_gemini_requires_key(tmp_path):
    llm = LLM(_cfg(tmp_path, "gemini"))  # 키 없음
    with pytest.raises(LLMError):
        llm.generate_text("안녕")


def test_generate_text_routes_to_provider(tmp_path, monkeypatch):
    llm = LLM(_cfg(tmp_path, "ollama"))
    captured = {}

    def fake_ollama(prompt, *, system=None, json_mode=False):
        captured["prompt"] = prompt
        captured["json_mode"] = json_mode
        return "결과 텍스트"

    monkeypatch.setattr(llm, "_ollama", fake_ollama)
    out = llm.generate_text("주제로 글 써줘", system="너는 의사")
    assert out == "결과 텍스트"
    assert captured["prompt"] == "주제로 글 써줘"


def test_generate_json_embeds_schema_and_parses(tmp_path, monkeypatch):
    llm = LLM(_cfg(tmp_path, "gemini", gemini_key="k"))
    schema = {"type": "object", "properties": {"title": {"type": "string"}}}

    def fake_gemini(prompt, *, system=None, max_tokens=4000, json_mode=False,
                    grounding=False):
        assert json_mode is True
        assert "title" in prompt  # 스키마가 프롬프트에 포함됨
        return '```json\n{"title": "여드름 흉터 치료"}\n```'

    monkeypatch.setattr(llm, "_gemini", fake_gemini)
    result = llm.generate_json("제목 만들어", schema=schema)
    assert result == {"title": "여드름 흉터 치료"}


def test_web_search_fallback_for_ollama(tmp_path, monkeypatch):
    llm = LLM(_cfg(tmp_path, "ollama"))
    monkeypatch.setattr(
        llm, "_ollama",
        lambda prompt, *, system=None, json_mode=False: f"[검색없음] {prompt[:5]}",
    )
    out = llm.web_search("요즘 피부과 트렌드")
    assert out.startswith("[검색없음]")


def test_parse_json_handles_fences_and_noise():
    assert _parse_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert _parse_json('설명...\n{"a": 2}\n끝') == {"a": 2}
    with pytest.raises(LLMError):
        _parse_json("JSON 없음")
