import logging
from datetime import datetime

import httpx

from app.clock import IST
from app.providers.base import Catalyst, ProviderError, sanitize_headline
from app.providers.upstream import Upstream

log = logging.getLogger(__name__)

DOC_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
SEEN_FORMAT = "%Y%m%dT%H%M%SZ"
MAX_RECORDS = 10

_client = httpx.Client(timeout=6.0)
_upstream = Upstream("gdelt", _client, rate_per_sec=0.2)


def fetch(company: str) -> list[Catalyst] | None:
    params = {
        "query": f'"{company}" sourcelang:english',
        "mode": "ArtList",
        "format": "json",
        "maxrecords": str(MAX_RECORDS),
        "timespan": "3d",
        "sort": "DateDesc",
    }
    try:
        response = _upstream.get("doc", company, DOC_URL, params)
    except ProviderError as exc:
        log.warning("provider=gdelt op=doc unavailable=%s", exc)
        return None
    if response.status_code != 200:
        return None
    try:
        articles = response.json().get("articles") or []
    except ValueError:
        log.warning("provider=gdelt op=doc unavailable=malformed_json")
        return None
    items = (_catalyst_from(article) for article in articles)
    return [item for item in items if item is not None]


def _catalyst_from(article: dict) -> Catalyst | None:
    headline = sanitize_headline(article.get("title") or "")
    if headline is None:
        return None
    try:
        published_at = datetime.strptime(article["seendate"], SEEN_FORMAT).astimezone(IST)
    except (KeyError, TypeError, ValueError):
        return None
    return Catalyst(
        headline=headline,
        source="gdelt",
        url=article.get("url") or "",
        published_at=published_at,
    )
