import logging
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

from app.providers.base import (
    BROWSER_USER_AGENT,
    Catalyst,
    ProviderError,
    sanitize_headline,
    validate_symbol,
)
from app.providers.transport import browser_client
from app.providers.upstream import Upstream

log = logging.getLogger(__name__)

FEED_URL = "https://feeds.finance.yahoo.com/rss/2.0/headline"

_client = browser_client({"User-Agent": BROWSER_USER_AGENT})
_upstream = Upstream("yahoo_rss", _client, rate_per_sec=1.0)


def fetch(symbol: str) -> list[Catalyst] | None:
    validate_symbol(symbol)
    params = {"s": symbol, "region": "IN", "lang": "en-IN"}
    try:
        response = _upstream.get("rss", symbol, FEED_URL, params)
    except ProviderError as exc:
        log.warning("provider=yahoo_rss op=rss symbol=%s unavailable=%s", symbol, exc)
        return None
    if response.status_code != 200:
        return None
    try:
        root = ET.fromstring(response.content)
    except ET.ParseError:
        log.warning("provider=yahoo_rss op=rss symbol=%s unavailable=malformed_xml", symbol)
        return None
    items = (_catalyst_from(item) for item in root.iter("item"))
    return [item for item in items if item is not None]


def _catalyst_from(item: ET.Element) -> Catalyst | None:
    headline = sanitize_headline(item.findtext("title") or "")
    published = item.findtext("pubDate")
    if headline is None or not published:
        return None
    try:
        published_at = parsedate_to_datetime(published)
    except (TypeError, ValueError):
        return None
    return Catalyst(
        headline=headline,
        source="yahoo_rss",
        url=item.findtext("link") or "",
        published_at=published_at,
    )
