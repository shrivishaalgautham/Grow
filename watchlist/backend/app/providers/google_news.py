import logging
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

from app.providers.base import (
    BROWSER_USER_AGENT,
    Catalyst,
    ProviderError,
    sanitize_headline,
)
from app.providers.transport import browser_client
from app.providers.upstream import Upstream

log = logging.getLogger(__name__)

FEED_URL = "https://news.google.com/rss/search"

_client = browser_client({"User-Agent": BROWSER_USER_AGENT})
_upstream = Upstream("google_news", _client, rate_per_sec=1.0)


def fetch(company: str) -> list[Catalyst] | None:
    params = {"q": f"{company} NSE", "hl": "en-IN", "gl": "IN", "ceid": "IN:en"}
    try:
        response = _upstream.get("rss", company, FEED_URL, params)
    except ProviderError as exc:
        log.warning("provider=google_news op=rss unavailable=%s", exc)
        return None
    if response.status_code != 200:
        return None
    try:
        root = ET.fromstring(response.content)
    except ET.ParseError:
        log.warning("provider=google_news op=rss unavailable=malformed_xml")
        return None
    items = (_catalyst_from(item) for item in root.iter("item"))
    return [item for item in items if item is not None]


def _catalyst_from(item: ET.Element) -> Catalyst | None:
    title = item.findtext("title") or ""
    publisher = item.findtext("source") or ""
    headline = sanitize_headline(title.removesuffix(f" - {publisher}") if publisher else title)
    published = item.findtext("pubDate")
    if headline is None or not published:
        return None
    try:
        published_at = parsedate_to_datetime(published)
    except (TypeError, ValueError):
        return None
    return Catalyst(
        headline=headline,
        source="google_news",
        url=item.findtext("link") or "",
        published_at=published_at,
    )
