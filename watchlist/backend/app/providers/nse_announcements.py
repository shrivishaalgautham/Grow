import logging
import re
import time
from datetime import date, datetime

import httpx

from app import clock
from app.clock import IST
from app.providers.base import BROWSER_USER_AGENT, Catalyst, ProviderError, sanitize_headline
from app.providers.upstream import Upstream

log = logging.getLogger(__name__)

HOME_URL = "https://www.nseindia.com/"
ANNOUNCEMENTS_URL = "https://www.nseindia.com/api/corporate-announcements"
SYMBOL_BASE_RE = re.compile(r"^[A-Z0-9&-]{1,20}$")
DATE_PARAM_FORMAT = "%d-%m-%Y"
ANNOUNCED_AT_FORMAT = "%d-%b-%Y %H:%M:%S"

_client = httpx.Client(
    headers={
        "User-Agent": BROWSER_USER_AGENT,
        "Accept": "application/json, text/html",
        "Referer": HOME_URL,
    },
    timeout=10.0,
)
_upstream = Upstream("nse", _client, rate_per_sec=1.0)


def fetch(symbol_base: str, since: date) -> list[Catalyst] | None:
    if not SYMBOL_BASE_RE.fullmatch(symbol_base):
        raise ValueError(f"invalid symbol {symbol_base!r}")
    params = {
        "index": "equities",
        "symbol": symbol_base,
        "from_date": since.strftime(DATE_PARAM_FORMAT),
        "to_date": clock.now().date().strftime(DATE_PARAM_FORMAT),
    }
    try:
        _refresh_cookies()
        response = _upstream.get("announcements", symbol_base, ANNOUNCEMENTS_URL, params)
    except (httpx.HTTPError, ProviderError) as exc:
        log.warning(
            "provider=nse op=announcements symbol=%s unavailable=%s",
            symbol_base,
            type(exc).__name__,
        )
        return None
    if response.status_code != 200:
        return None
    items = (_catalyst_from(row) for row in response.json())
    return [item for item in items if item is not None and item.published_at.date() >= since]


def _refresh_cookies() -> None:
    _upstream.bucket.acquire()
    started = time.monotonic()
    response = _client.get(HOME_URL)
    log.info(
        "provider=nse op=cookies symbol=- status=%s ms=%d",
        response.status_code,
        int((time.monotonic() - started) * 1000),
    )


def _catalyst_from(row: dict) -> Catalyst | None:
    detail = row.get("attchmntText") or ""
    subject = row.get("desc") or ""
    headline = sanitize_headline(
        f"{subject}: {detail}" if subject and detail else subject or detail
    )
    if headline is None:
        return None
    try:
        published_at = datetime.strptime(row["an_dt"], ANNOUNCED_AT_FORMAT).replace(tzinfo=IST)
    except (KeyError, TypeError, ValueError):
        log.warning(
            "provider=nse op=announcements skipped=malformed_row seq_id=%s", row.get("seq_id")
        )
        return None
    return Catalyst(
        headline=headline,
        source="nse",
        url=row.get("attchmntFile") or "",
        published_at=published_at,
    )
