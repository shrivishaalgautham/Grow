import logging
import time

import httpx

from app.config import settings

log = logging.getLogger(__name__)

CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"
TIMEOUT_S = 15.0
TEMPERATURE = 0.2

_client = httpx.Client(timeout=TIMEOUT_S)


def complete(messages: list[dict[str, str]], max_tokens: int) -> str | None:
    if not settings.openrouter_api_key:
        return None
    for model in settings.openrouter_models:
        content = _complete_with(model, messages, max_tokens)
        if content is not None:
            return content
    return None


def _complete_with(model: str, messages: list[dict[str, str]], max_tokens: int) -> str | None:
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": TEMPERATURE,
        "provider": {"data_collection": "deny"},
    }
    headers = {"Authorization": f"Bearer {settings.openrouter_api_key}"}
    started = time.monotonic()
    try:
        response = _client.post(CHAT_URL, json=payload, headers=headers)
    except httpx.HTTPError as exc:
        _log(model, f"error={type(exc).__name__}", started)
        return None
    if response.status_code != 200:
        _log(model, f"status={response.status_code}", started)
        return None
    content, tokens = _content(response)
    _log(model, f"status=200 tokens={tokens} empty={content is None}", started)
    return content


def _content(response: httpx.Response) -> tuple[str | None, int | None]:
    try:
        body = response.json()
        content = body["choices"][0]["message"]["content"]
        tokens = (body.get("usage") or {}).get("total_tokens")
    except (ValueError, KeyError, IndexError, TypeError):
        return None, None
    text = content.strip() if isinstance(content, str) else ""
    return (text or None), tokens


def _log(model: str, outcome: str, started: float) -> None:
    log.info("llm model=%s %s ms=%d", model, outcome, int((time.monotonic() - started) * 1000))
