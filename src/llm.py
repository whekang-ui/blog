"""Claude(Anthropic) API 래퍼.

콘텐츠/주제/SEO 모듈이 공통으로 쓰는 얇은 래퍼. 세 가지 호출 형태를 제공한다:
- generate_text: 일반 텍스트 생성 (긴 출력은 스트리밍)
- generate_json: 구조화 출력(JSON schema) — 제목/태그/SEO 점수 등
- web_search: 서버사이드 웹검색 툴로 최신 트렌드 조사

모델 기본값은 claude-opus-4-8 (피부과 전문성·정확성 요구). 적응형 사고 + effort=high.
"""

from __future__ import annotations

import json
from typing import Any

try:
    import anthropic
except ImportError:  # 미설치 환경에서도 import 가능하게
    anthropic = None  # type: ignore

from .config import Config

DEFAULT_MODEL = "claude-opus-4-8"


class LLMError(RuntimeError):
    pass


class LLM:
    """Anthropic 클라이언트 래퍼."""

    def __init__(self, config: Config, model: str | None = None) -> None:
        if anthropic is None:
            raise LLMError(
                "anthropic 패키지가 설치되지 않았습니다. `pip install -r requirements.txt`"
            )
        if not config.secrets.anthropic_api_key:
            raise LLMError("ANTHROPIC_API_KEY 가 설정되지 않았습니다 (.env 확인).")
        self._client = anthropic.Anthropic(api_key=config.secrets.anthropic_api_key)
        self.model = model or config.get("content.model", DEFAULT_MODEL)

    def generate_text(
        self,
        prompt: str,
        *,
        system: str | None = None,
        max_tokens: int = 8000,
        effort: str = "high",
    ) -> str:
        """긴 텍스트(본문 등)를 스트리밍으로 생성해 전체 문자열을 반환."""
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens,
            "thinking": {"type": "adaptive"},
            "output_config": {"effort": effort},
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system
        try:
            with self._client.messages.stream(**kwargs) as stream:
                message = stream.get_final_message()
        except Exception as exc:  # noqa: BLE001 - 사용자에게 원인 전달
            raise LLMError(f"Claude 텍스트 생성 실패: {exc}") from exc
        return _join_text(message)

    def generate_json(
        self,
        prompt: str,
        *,
        schema: dict[str, Any],
        system: str | None = None,
        max_tokens: int = 4000,
        effort: str = "high",
    ) -> dict[str, Any]:
        """JSON schema 로 구조화 출력. 결과를 dict 로 파싱해 반환."""
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens,
            "thinking": {"type": "adaptive"},
            "output_config": {
                "effort": effort,
                "format": {"type": "json_schema", "schema": schema},
            },
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system
        try:
            message = self._client.messages.create(**kwargs)
        except Exception as exc:  # noqa: BLE001
            raise LLMError(f"Claude JSON 생성 실패: {exc}") from exc
        text = _join_text(message)
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise LLMError(f"JSON 파싱 실패: {exc}\n원문: {text[:500]}") from exc

    def web_search(
        self,
        prompt: str,
        *,
        system: str | None = None,
        max_uses: int = 5,
        max_tokens: int = 6000,
    ) -> str:
        """서버사이드 웹검색 툴로 최신 정보를 조사해 텍스트로 반환."""
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens,
            "tools": [
                {
                    "type": "web_search_20260209",
                    "name": "web_search",
                    "max_uses": max_uses,
                }
            ],
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system
        try:
            message = self._client.messages.create(**kwargs)
        except Exception as exc:  # noqa: BLE001
            raise LLMError(f"Claude 웹검색 실패: {exc}") from exc
        return _join_text(message)


def _join_text(message: Any) -> str:
    """응답 content 블록들에서 text 만 이어붙인다."""
    parts: list[str] = []
    for block in getattr(message, "content", []) or []:
        if getattr(block, "type", None) == "text":
            parts.append(block.text)
    return "".join(parts).strip()
