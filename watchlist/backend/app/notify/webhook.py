import hashlib
import hmac
import ipaddress
import json
import logging
import socket
from urllib.parse import urlparse

import httpx

log = logging.getLogger(__name__)

TIMEOUT_S = 10.0

_client = httpx.Client(timeout=TIMEOUT_S)


def is_safe_target(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return False
    try:
        resolved = ipaddress.ip_address(socket.gethostbyname(parsed.hostname))
    except (OSError, ValueError):
        return False
    return not (
        resolved.is_private
        or resolved.is_loopback
        or resolved.is_link_local
        or resolved.is_reserved
        or resolved.is_multicast
    )


def send(url: str, secret: str, payload: dict) -> bool:
    if not is_safe_target(url):
        log.warning("webhook_blocked host=%s reason=unsafe_target", _host(url))
        return False
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    try:
        response = _client.post(
            url,
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-Watchlist-Signature": f"sha256={signature}",
            },
        )
    except httpx.HTTPError as exc:
        log.warning("webhook_failed host=%s error=%s", _host(url), type(exc).__name__)
        return False
    if response.status_code >= 400:
        log.warning("webhook_failed host=%s status=%d", _host(url), response.status_code)
        return False
    return True


def _host(url: str) -> str:
    return urlparse(url).hostname or "unknown"
