"""AI 비임상 이미지 생성 (pluggable).

피부/스킨케어를 뜻하는 개념·일러스트·모델 느낌(예: 모델이 얼굴을 매만지는 장면, 윤기 나는 피부
표현 등)의 '비임상' 이미지만 생성한다. 의료법상 가짜 임상/시술 전후/환자 사진은 절대 생성 금지.

외부 이미지 생성 API 는 교체 가능(pluggable)하다. IMAGE_API_PROVIDER 가 비어있으면 비활성.
현재는 'openai' 프로바이더를 지원한다. 키/프로바이더/패키지가 없으면 None 을 반환(인포그래픽 폴백).
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

from ..config import Config

# 임상/환자/전후 의도를 차단하기 위한 금지어 (프롬프트 가드)
_FORBIDDEN = (
    "환자", "시술 전", "시술 후", "비포", "애프터", "before", "after",
    "병변", "수술", "치료 결과", "실제 사례", "patient", "lesion", "surgery",
)

# 비임상 안전 스타일 프리픽스
_SAFE_STYLE = (
    "professional clean editorial photo, beauty/skincare concept, soft natural light, "
    "non-clinical, no medical procedure, no patient, no before/after, "
    "healthy glowing skin aesthetic, Korean beauty mood"
)

_DEFAULT_SIZE = "1024x1024"


def is_clinical_intent(description: str) -> bool:
    """설명에 임상/환자/전후 의도가 포함되어 있으면 True (생성 금지 대상)."""
    low = description.lower()
    return any(bad.lower() in low for bad in _FORBIDDEN)


def build_prompt(description: str) -> str:
    """비임상 안전 스타일을 입힌 최종 프롬프트."""
    return f"{_SAFE_STYLE}. Subject: {description}"


def generate_ai_image(config: Config, description: str, out_path: Path) -> str | None:
    """비임상 AI 이미지를 생성해 경로를 반환. 실패/비활성/임상의도면 None."""
    if not config.secrets.has_image_api:
        return None
    if is_clinical_intent(description):
        # 의료법 가드: 임상/환자 이미지는 생성하지 않는다.
        return None

    provider = config.secrets.image_api_provider.lower()
    prompt = build_prompt(description)
    size = config.get("images.ai_size", _DEFAULT_SIZE)

    if provider == "openai":
        return _openai_image(config, prompt, out_path, size=size)

    # 알 수 없는 프로바이더 — 미지원
    return None


def _build_openai_client(api_key: str) -> Any:
    """OpenAI 클라이언트 생성 (테스트에서 monkeypatch 하기 쉽도록 분리)."""
    from openai import OpenAI  # 선택적 의존성

    return OpenAI(api_key=api_key)


def _openai_image(
    config: Config, prompt: str, out_path: Path, *, size: str = _DEFAULT_SIZE
) -> str | None:
    """OpenAI Images API 구현. 실패 시 None (인포그래픽 폴백)."""
    try:
        client = _build_openai_client(config.secrets.image_api_key)
    except ImportError:
        return None
    except Exception:  # noqa: BLE001
        return None

    try:
        result = client.images.generate(
            model="gpt-image-1", prompt=prompt, size=size, n=1
        )
        b64 = result.data[0].b64_json
        if not b64:
            return None
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(base64.b64decode(b64))
        return str(out_path)
    except Exception:  # noqa: BLE001 - 이미지 실패는 치명적이지 않음(폴백)
        return None
