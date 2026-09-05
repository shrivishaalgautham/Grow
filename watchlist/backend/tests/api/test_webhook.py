import hashlib
import hmac
import json

import httpx
import respx

from app.notify import webhook


def test_public_https_host_is_safe():
    assert webhook.is_safe_target("https://example.com/hook") is True


def test_localhost_is_unsafe():
    assert webhook.is_safe_target("http://localhost/hook") is False


def test_loopback_ip_is_unsafe():
    assert webhook.is_safe_target("http://127.0.0.1:8000/hook") is False


def test_private_ip_is_unsafe():
    assert webhook.is_safe_target("http://10.0.0.5/hook") is False


def test_non_http_scheme_is_unsafe():
    assert webhook.is_safe_target("ftp://example.com/hook") is False


@respx.mock
def test_send_signs_the_body_with_the_shared_secret():
    route = respx.post("https://example.com/hook").mock(return_value=httpx.Response(200))

    ok = webhook.send("https://example.com/hook", "shh", {"a": 1})

    assert ok is True
    sent = route.calls.last.request
    body = sent.content
    expected = hmac.new(b"shh", body, hashlib.sha256).hexdigest()
    assert sent.headers["X-Watchlist-Signature"] == f"sha256={expected}"
    assert json.loads(body) == {"a": 1}


@respx.mock
def test_send_reports_failure_on_a_non_2xx_response():
    respx.post("https://example.com/hook").mock(return_value=httpx.Response(500))

    assert webhook.send("https://example.com/hook", "shh", {"a": 1}) is False


def test_send_never_calls_an_unsafe_target():
    assert webhook.send("http://localhost/hook", "shh", {"a": 1}) is False
