import logging
import re
from dataclasses import dataclass

import httpx

from app.config import settings

log = logging.getLogger(__name__)

MODEL = "gemini-2.5-flash"
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"
TIMEOUT_S = 25.0
TEMPERATURE = 0.2
MAX_CHARS = 900
BANNED_WORDS = ("bullish", "bearish", "buy", "sell", "hold", "opportunity", "risk", "target")
MARKDOWN_LINK_RE = re.compile(r"\]\(")

_client = httpx.Client(timeout=TIMEOUT_S)


@dataclass(frozen=True)
class GroundedResult:
    text: str
    source_titles: list[str]


def is_configured() -> bool:
    return bool(settings.google_api_key)


def ground(system: str, prompt: str, max_tokens: int) -> GroundedResult | None:
    if not is_configured():
        return None
    body = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"parts": [{"text": prompt}]}],
        "tools": [{"google_search": {}}],
        "generationConfig": {"maxOutputTokens": max_tokens, "temperature": TEMPERATURE},
    }
    try:
        response = _client.post(
            API_URL,
            json=body,
            headers={
                "x-goog-api-key": settings.google_api_key,
                "Content-Type": "application/json",
            },
        )
    except httpx.HTTPError as exc:
        log.warning("gemini_error error=%s", type(exc).__name__)
        return None
    if response.status_code != 200:
        log.warning("gemini_error status=%d", response.status_code)
        return None
    return _parse(response.json())


def validate(text: str) -> str | None:
    if not text.strip():
        return "empty"
    if len(text) > MAX_CHARS:
        return "too_long"
    if MARKDOWN_LINK_RE.search(text):
        return "markdown_link"
    lowered = text.lower()
    for word in BANNED_WORDS:
        if re.search(rf"\b{word}\b", lowered):
            return f"banned_word:{word}"
    return None


def _parse(payload: dict) -> GroundedResult | None:
    try:
        candidate = payload["candidates"][0]
        parts = candidate["content"]["parts"]
        text = "".join(part.get("text", "") for part in parts).strip()
    except (KeyError, IndexError, TypeError):
        log.warning("gemini_error error=malformed_response")
        return None
    if not text:
        return None
    grounding = candidate.get("groundingMetadata") or {}
    chunks = grounding.get("groundingChunks") or []
    titles = [
        chunk["web"]["title"] for chunk in chunks if chunk.get("web", {}).get("title")
    ]
    return GroundedResult(text=text, source_titles=titles[:5])
