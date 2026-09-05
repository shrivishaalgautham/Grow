import httpx
import respx

from app.ai import gemini


def _response(text: str, titles: list[str] | None = None) -> dict:
    candidate = {"content": {"parts": [{"text": text}]}}
    if titles is not None:
        candidate["groundingMetadata"] = {
            "groundingChunks": [{"web": {"title": title}} for title in titles]
        }
    return {"candidates": [candidate]}


def test_is_configured_reflects_the_api_key(monkeypatch):
    monkeypatch.setattr(gemini.settings, "google_api_key", "")
    assert gemini.is_configured() is False
    monkeypatch.setattr(gemini.settings, "google_api_key", "key")
    assert gemini.is_configured() is True


@respx.mock
def test_ground_returns_text_and_source_titles(monkeypatch):
    monkeypatch.setattr(gemini.settings, "google_api_key", "key")
    route = respx.post(gemini.API_URL).mock(
        return_value=httpx.Response(200, json=_response("Explanation text.", ["example.com"]))
    )

    result = gemini.ground("system", "prompt", 500)

    assert result is not None
    assert result.text == "Explanation text."
    assert result.source_titles == ["example.com"]
    request_body = route.calls.last.request.content
    assert b"google_search" in request_body
    assert route.calls.last.request.headers["x-goog-api-key"] == "key"


@respx.mock
def test_ground_returns_none_when_the_api_key_is_missing(monkeypatch):
    monkeypatch.setattr(gemini.settings, "google_api_key", "")

    assert gemini.ground("system", "prompt", 500) is None


@respx.mock
def test_ground_returns_none_on_a_non_200_response(monkeypatch):
    monkeypatch.setattr(gemini.settings, "google_api_key", "key")
    respx.post(gemini.API_URL).mock(return_value=httpx.Response(500))

    assert gemini.ground("system", "prompt", 500) is None


@respx.mock
def test_ground_returns_none_on_a_malformed_response(monkeypatch):
    monkeypatch.setattr(gemini.settings, "google_api_key", "key")
    respx.post(gemini.API_URL).mock(return_value=httpx.Response(200, json={"candidates": []}))

    assert gemini.ground("system", "prompt", 500) is None


def test_validate_rejects_banned_words():
    assert gemini.validate("This is a strong buy.") == "banned_word:buy"


def test_validate_rejects_markdown_links():
    assert gemini.validate("See [this](https://example.com) filing.") == "markdown_link"


def test_validate_rejects_empty_text():
    assert gemini.validate("   ") == "empty"


def test_validate_accepts_clean_text():
    assert gemini.validate("The move coincided with a filing reported by a major outlet.") is None
