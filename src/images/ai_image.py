"""AI 비임상 이미지 생성 (pluggable).

피부/스킨케어를 뜻하는 개념·일러스트·모델 느낌(예: 모델이 얼굴을 매만지는 장면, 윤기 나는 피부
표현 등)의 '비임상' 이미지만 생성한다. 의료법상 가짜 임상/시술 전후/환자 사진은 절대 생성 금지.

지원 제공자(IMAGE_API_PROVIDER):
- "huggingface"(또는 "hf") : Hugging Face Inference API(무료 등급). IMAGE_API_KEY=hf_... 필요.
- "gemini" : Google Gemini 이미지 생성(무료 등급은 0인 경우 많음). IMAGE_API_KEY 필요.
- "openai" : OpenAI Images(유료). IMAGE_API_KEY 필요.
키/프로바이더가 없거나 임상 의도면 None 을 반환(인포그래픽으로 폴백). 실패 사유는
generate_ai_image_verbose 로 받을 수 있다.
"""

from __future__ import annotations

import base64
import time
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
_DEFAULT_GEMINI_IMAGE_MODEL = "gemini-2.5-flash-image"
_DEFAULT_HF_MODEL = "black-forest-labs/FLUX.1-schnell"
# 2024~ Hugging Face 는 추론 API 를 router.huggingface.co 로 이전함(구 api-inference 는
# DNS 가 안 잡히는 경우가 있음). 필요시 config images.hf_endpoint 로 교체 가능.
_DEFAULT_HF_ENDPOINT = "https://router.huggingface.co/hf-inference/models/{model}"
_GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)


def is_clinical_intent(description: str) -> bool:
    """설명에 임상/환자/전후 의도가 포함되어 있으면 True (생성 금지 대상)."""
    low = description.lower()
    return any(bad.lower() in low for bad in _FORBIDDEN)


def build_prompt(description: str) -> str:
    """비임상 안전 스타일을 입힌 최종 프롬프트."""
    return f"{_SAFE_STYLE}. Subject: {description}"


def generate_ai_image(config: Config, description: str, out_path: Path) -> str | None:
    """비임상 AI 이미지를 생성해 경로를 반환. 실패/비활성/임상의도면 None."""
    path, _reason = generate_ai_image_verbose(config, description, out_path)
    return path


def generate_ai_image_verbose(
    config: Config, description: str, out_path: Path
) -> tuple[str | None, str | None]:
    """AI 이미지 생성. (경로, 실패사유) 반환.

    성공: (경로, None). 실패: (None, "사유 문자열"). 사유는 로그/UI 표시용.
    """
    if not config.secrets.has_image_api:
        return None, "이미지 API 미설정(IMAGE_API_PROVIDER/KEY)"
    if is_clinical_intent(description):
        return None, "임상/환자 사진 의도 → 의료법상 AI 생성 차단"

    provider = config.secrets.image_api_provider.lower()
    prompt = build_prompt(description)

    if provider in ("huggingface", "hf"):
        return _hf_image(config, prompt, out_path)
    if provider == "gemini":
        return _gemini_image(config, prompt, out_path)
    if provider == "openai":
        size = config.get("images.ai_size", _DEFAULT_SIZE)
        return _openai_image(config, prompt, out_path, size=size)

    return None, f"미지원 IMAGE_API_PROVIDER='{provider}' (huggingface/gemini/openai 중 하나)"


# ---- Hugging Face 이미지 -----------------------------------------------
def _hf_post(endpoint: str, token: str, payload: dict[str, Any]):
    """HF Inference API 호출(테스트에서 monkeypatch 하기 쉽도록 분리). Response 반환."""
    import requests

    return requests.post(
        endpoint,
        headers={"Authorization": f"Bearer {token}", "Accept": "image/png"},
        json=payload,
        timeout=120,
    )


def _hf_image(config: Config, prompt: str, out_path: Path) -> tuple[str | None, str | None]:
    """Hugging Face 텍스트→이미지. 모델 로딩(503) 시 짧게 재시도. (경로,사유)."""
    token = config.secrets.image_api_key
    model = config.get("images.ai_model", _DEFAULT_HF_MODEL)
    endpoint = config.get("images.hf_endpoint", _DEFAULT_HF_ENDPOINT).format(model=model)
    payload = {"inputs": prompt}

    for attempt in range(3):
        try:
            resp = _hf_post(endpoint, token, payload)
        except Exception as exc:  # noqa: BLE001
            msg = str(exc)
            if "resolve" in msg or "NameResolution" in msg or "getaddrinfo" in msg:
                return None, (
                    "HF 주소를 찾지 못함(DNS). huggingface.co 접속이 막혔을 수 있어요 "
                    "(병원/회사 네트워크·방화벽). 브라우저로 huggingface.co 가 열리는지 확인하거나 "
                    "다른 네트워크에서 시도하세요."
                )
            return None, f"HF 네트워크 오류: {msg[:200]}"

        ctype = resp.headers.get("content-type", "")
        if resp.status_code == 200 and ctype.startswith("image/"):
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_bytes(resp.content)
            return str(out_path), None

        # 모델 콜드스타트(로딩) — 잠시 후 재시도
        if resp.status_code == 503 and attempt < 2:
            wait = 8.0
            try:
                wait = float(resp.json().get("estimated_time", wait))
            except Exception:  # noqa: BLE001
                pass
            time.sleep(min(wait, 30))
            continue

        # 그 외 오류 — 사유 추출
        detail = ""
        try:
            detail = resp.json().get("error", "")
        except Exception:  # noqa: BLE001
            detail = (resp.text or "")[:160]
        return None, f"HF HTTP {resp.status_code} {detail}".strip()

    return None, "HF 모델 로딩 반복 실패(503). 잠시 후 다시 시도하세요."


# ---- Gemini 이미지 ------------------------------------------------------
def _gemini_generate_content(model: str, key: str, body: dict[str, Any]) -> dict[str, Any]:
    """Gemini generateContent 호출(테스트에서 monkeypatch 하기 쉽도록 분리)."""
    import requests

    resp = requests.post(
        _GEMINI_URL.format(model=model), params={"key": key}, json=body, timeout=120
    )
    resp.raise_for_status()
    return resp.json()


def _gemini_image(
    config: Config, prompt: str, out_path: Path
) -> tuple[str | None, str | None]:
    """Gemini 이미지 생성. (경로, 사유) 반환."""
    key = config.secrets.image_api_key
    model = config.get("images.ai_model", _DEFAULT_GEMINI_IMAGE_MODEL)
    body = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]},
    }
    try:
        data = _gemini_generate_content(model, key, body)
    except Exception as exc:  # noqa: BLE001
        return None, f"Gemini 오류: {exc}"

    img_bytes = _extract_inline_image(data)
    if not img_bytes:
        return None, "Gemini 응답에 이미지 없음(텍스트만/거부)"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(img_bytes)
    return str(out_path), None


def _extract_inline_image(data: dict[str, Any]) -> bytes | None:
    """Gemini 응답 parts 에서 첫 inlineData(이미지) 를 디코드해 반환."""
    for cand in data.get("candidates", []) or []:
        for part in (cand.get("content", {}) or {}).get("parts", []) or []:
            inline = part.get("inlineData") or part.get("inline_data")
            if inline and inline.get("data"):
                try:
                    return base64.b64decode(inline["data"])
                except Exception:  # noqa: BLE001
                    return None
    return None


# ---- OpenAI 이미지 (선택, 유료) ----------------------------------------
def _build_openai_client(api_key: str) -> Any:
    """OpenAI 클라이언트 생성 (테스트에서 monkeypatch 하기 쉽도록 분리)."""
    from openai import OpenAI  # 선택적 의존성

    return OpenAI(api_key=api_key)


def _openai_image(
    config: Config, prompt: str, out_path: Path, *, size: str = _DEFAULT_SIZE
) -> tuple[str | None, str | None]:
    """OpenAI Images API 구현. (경로, 사유) 반환."""
    try:
        client = _build_openai_client(config.secrets.image_api_key)
    except ImportError:
        return None, "openai 패키지 미설치(pip install openai)"
    except Exception as exc:  # noqa: BLE001
        return None, f"OpenAI 클라이언트 오류: {exc}"

    try:
        result = client.images.generate(
            model="gpt-image-1", prompt=prompt, size=size, n=1
        )
        b64 = result.data[0].b64_json
        if not b64:
            return None, "OpenAI 응답에 이미지 없음"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(base64.b64decode(b64))
        return str(out_path), None
    except Exception as exc:  # noqa: BLE001
        return None, f"OpenAI 오류: {exc}"
