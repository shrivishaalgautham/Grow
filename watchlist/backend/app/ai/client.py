import logging
from dataclasses import dataclass

import httpx

from app.config import settings

log = logging.getLogger(__name__)

TIMEOUT_S = 25.0
TEMPERATURE = 0.2

_client = httpx.Client(timeout=TIMEOUT_S)


@dataclass(frozen=True)
class Completion:
    text: str
    model: str


def is_configured() -> bool:
    return bool(settings.openrouter_api_key)


def complete(purpose: str, system: str, user: str, max_tokens: int) -> Completion | None:
    if not is_configured():
        return None
    for model in settings.openrouter_models:
        completion = _try_model(purpose, model, system, user, max_tokens)
        if completion is not None:
            return completion
    return None


def _try_model(
    purpose: str, model: str, system: str, user: str, max_tokens: int
) -> Completion | None:
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": max_tokens,
        "temperature": TEMPERATURE,
        "provider": {"data_collection": "deny"},
    }
    try:
        response = _client.post(
            f"{settings.openrouter_base_url}/chat/completions",
            json=body,
            headers={"Authorization": f"Bearer {settings.openrouter_api_key}"},
        )
    except httpx.HTTPError as exc:
        log.warning("llm purpose=%s model=%s error=%s", purpose, model, type(exc).__name__)
        return None
    if response.status_code != 200:
        log.warning("llm purpose=%s model=%s status=%d", purpose, model, response.status_code)
        return None
    try:
        payload = response.json()
        text = payload["choices"][0]["message"]["content"]
        usage = payload.get("usage") or {}
    except (ValueError, KeyError, IndexError, TypeError):
        log.warning("llm purpose=%s model=%s error=malformed_response", purpose, model)
        return None
    if not isinstance(text, str) or not text.strip():
        log.warning("llm purpose=%s model=%s error=empty_response", purpose, model)
        return None
    log.info(
        "llm purpose=%s model=%s data_collection=deny prompt_tokens=%s completion_tokens=%s",
        purpose,
        model,
        usage.get("prompt_tokens"),
        usage.get("completion_tokens"),
    )
    return Completion(text=text.strip(), model=model)
