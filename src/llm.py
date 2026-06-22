"""LLM 래퍼 (제공자 교체 가능 / pluggable).

콘텐츠·주제·SEO 모듈이 공통으로 쓰는 얇은 래퍼. 세 가지 호출을 제공한다:
- generate_text: 일반 텍스트 생성(본문 등)
- generate_json: 구조화 출력(JSON) — 제목/태그/SEO 점수 등
- web_search: 최신 트렌드 조사(가능한 제공자만; 아니면 모델 지식 기반으로 폴백)

지원 제공자(config "content.provider"):
- "gemini"   : Google Gemini  — 무료 등급 사용 가능(권장). GEMINI_API_KEY 필요.
- "ollama"   : 로컬 Ollama    — 완전 무료·비공개. 키 불필요(PC에 ollama 설치/실행).
- "anthropic": Claude         — 유료. ANTHROPIC_API_KEY 필요(선택).

추가 SDK 없이 requests 로 REST 를 호출한다(anthropic 만 공식 SDK 사용).
"""

from __future__ import annotations

import json
import re
from typing import Any

try:
    import requests
except ImportError:  # 미설치 환경 보호
    requests = None  # type: ignore

from .config import Config

# 제공자별 기본 모델
DEFAULT_MODELS = {
    "gemini": "gemini-2.0-flash",
    "ollama": "qwen2.5:7b",       # 한국어 양호한 오픈모델 (사용자가 변경 가능)
    "anthropic": "claude-opus-4-8",
}

_GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)
_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


class LLMError(RuntimeError):
    pass


class LLM:
    """제공자 중립 LLM 래퍼."""

    def __init__(self, config: Config, model: str | None = None) -> None:
        self.config = config
        self.provider = (config.get("content.provider", "gemini") or "gemini").lower()
        self.model = (
            model
            or config.get("content.model")
            or DEFAULT_MODELS.get(self.provider, DEFAULT_MODELS["gemini"])
        )
        if requests is None and self.provider in ("gemini", "ollama"):
            raise LLMError("requests 패키지가 필요합니다. `pip install -r requirements.txt`")

    # ---- public API -----------------------------------------------------
    def generate_text(
        self, prompt: str, *, system: str | None = None, max_tokens: int = 8000,
        effort: str = "high",  # anthropic 전용; 다른 제공자는 무시
    ) -> str:
        if self.provider == "gemini":
            return self._gemini(prompt, system=system, max_tokens=max_tokens)
        if self.provider == "ollama":
            return self._ollama(prompt, system=system)
        if self.provider == "anthropic":
            return self._anthropic_text(prompt, system=system, max_tokens=max_tokens,
                                        effort=effort)
        raise LLMError(f"알 수 없는 provider: {self.provider}")

    def generate_json(
        self, prompt: str, *, schema: dict[str, Any], system: str | None = None,
        max_tokens: int = 4000, effort: str = "high",
    ) -> dict[str, Any]:
        # 스키마를 프롬프트에 명시해 제공자 호환성을 높인다(JSON 모드와 병행).
        schema_hint = (
            "\n\n반드시 아래 JSON 스키마에 맞는 'JSON 객체만' 출력하라(설명·코드펜스 금지):\n"
            + json.dumps(schema, ensure_ascii=False)
        )
        full = prompt + schema_hint
        if self.provider == "gemini":
            text = self._gemini(full, system=system, max_tokens=max_tokens, json_mode=True)
        elif self.provider == "ollama":
            text = self._ollama(full, system=system, json_mode=True)
        elif self.provider == "anthropic":
            return self._anthropic_json(prompt, schema=schema, system=system,
                                        max_tokens=max_tokens, effort=effort)
        else:
            raise LLMError(f"알 수 없는 provider: {self.provider}")
        return _parse_json(text)

    def web_search(
        self, prompt: str, *, system: str | None = None, max_uses: int = 5,
        max_tokens: int = 6000,
    ) -> str:
        if self.provider == "gemini":
            return self._gemini(prompt, system=system, max_tokens=max_tokens,
                                 grounding=True)
        if self.provider == "anthropic":
            return self._anthropic_web_search(prompt, system=system, max_uses=max_uses,
                                              max_tokens=max_tokens)
        # ollama 등 검색 미지원 → 모델 지식 기반으로 폴백
        note = ("\n\n(참고: 실시간 웹검색을 쓸 수 없어, 보유 지식 기반으로 일반적인 최신 경향을 "
                "추정해 답한다. 불확실한 수치는 단정하지 않는다.)")
        return self.generate_text(prompt + note, system=system, max_tokens=max_tokens)

    # ---- Gemini (REST) --------------------------------------------------
    def _gemini(
        self, prompt: str, *, system: str | None, max_tokens: int,
        json_mode: bool = False, grounding: bool = False,
    ) -> str:
        key = self.config.secrets.gemini_api_key
        if not key:
            raise LLMError(
                "GEMINI_API_KEY 가 없습니다. https://aistudio.google.com/apikey 에서 "
                "무료 키를 발급해 .env 에 넣으세요."
            )
        body: dict[str, Any] = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": max_tokens},
        }
        if system:
            body["system_instruction"] = {"parts": [{"text": system}]}
        if json_mode:
            body["generationConfig"]["responseMimeType"] = "application/json"
        if grounding:
            body["tools"] = [{"google_search": {}}]
        try:
            resp = requests.post(
                _GEMINI_URL.format(model=self.model),
                params={"key": key}, json=body, timeout=120,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:  # noqa: BLE001
            raise LLMError(f"Gemini 호출 실패: {exc}") from exc
        return _gemini_text(data)

    # ---- Ollama (REST, local) ------------------------------------------
    def _ollama(
        self, prompt: str, *, system: str | None, json_mode: bool = False
    ) -> str:
        host = self.config.get("content.ollama_host", "http://localhost:11434")
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        body: dict[str, Any] = {"model": self.model, "messages": messages,
                                "stream": False}
        if json_mode:
            body["format"] = "json"
        try:
            resp = requests.post(f"{host}/api/chat", json=body, timeout=600)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:  # noqa: BLE001
            raise LLMError(
                f"Ollama 호출 실패: {exc}. Ollama 가 설치·실행 중인지, 모델('{self.model}')이 "
                f"받아졌는지 확인하세요(예: `ollama pull {self.model}`)."
            ) from exc
        return (data.get("message", {}) or {}).get("content", "").strip()

    # ---- Anthropic (SDK, optional/paid) --------------------------------
    def _anthropic_client(self) -> Any:
        try:
            import anthropic
        except ImportError as exc:
            raise LLMError("anthropic 패키지가 없습니다. `pip install anthropic`") from exc
        if not self.config.secrets.anthropic_api_key:
            raise LLMError("ANTHROPIC_API_KEY 가 없습니다(.env).")
        return anthropic.Anthropic(api_key=self.config.secrets.anthropic_api_key)

    def _anthropic_text(self, prompt, *, system, max_tokens, effort) -> str:
        client = self._anthropic_client()
        kwargs: dict[str, Any] = {
            "model": self.model, "max_tokens": max_tokens,
            "thinking": {"type": "adaptive"}, "output_config": {"effort": effort},
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system
        with client.messages.stream(**kwargs) as stream:
            return _anthropic_join(stream.get_final_message())

    def _anthropic_json(self, prompt, *, schema, system, max_tokens, effort) -> dict:
        client = self._anthropic_client()
        kwargs: dict[str, Any] = {
            "model": self.model, "max_tokens": max_tokens,
            "thinking": {"type": "adaptive"},
            "output_config": {"effort": effort,
                              "format": {"type": "json_schema", "schema": schema}},
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system
        message = client.messages.create(**kwargs)
        return _parse_json(_anthropic_join(message))

    def _anthropic_web_search(self, prompt, *, system, max_uses, max_tokens) -> str:
        client = self._anthropic_client()
        kwargs: dict[str, Any] = {
            "model": self.model, "max_tokens": max_tokens,
            "tools": [{"type": "web_search_20260209", "name": "web_search",
                       "max_uses": max_uses}],
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system
        return _anthropic_join(client.messages.create(**kwargs))


# ---- helpers -----------------------------------------------------------
def _gemini_text(data: dict[str, Any]) -> str:
    parts = []
    for cand in data.get("candidates", []) or []:
        for part in (cand.get("content", {}) or {}).get("parts", []) or []:
            if "text" in part:
                parts.append(part["text"])
    return "".join(parts).strip()


def _anthropic_join(message: Any) -> str:
    parts = []
    for block in getattr(message, "content", []) or []:
        if getattr(block, "type", None) == "text":
            parts.append(block.text)
    return "".join(parts).strip()


def _parse_json(text: str) -> dict[str, Any]:
    """모델 출력에서 JSON 객체를 견고하게 파싱(코드펜스/잡텍스트 제거)."""
    text = (text or "").strip()
    if not text:
        raise LLMError("빈 응답(JSON 없음).")
    # ```json ... ``` 펜스 제거
    m = _FENCE_RE.search(text)
    if m:
        text = m.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # 첫 { ~ 마지막 } 사이만 추출 재시도
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError as exc:
                raise LLMError(f"JSON 파싱 실패: {exc}\n원문: {text[:400]}") from exc
        raise LLMError(f"JSON 파싱 실패.\n원문: {text[:400]}")
