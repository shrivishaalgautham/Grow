from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from app.providers.base import LiveQuote

DISPUTE_THRESHOLD_PCT = 0.5
STALE_AFTER_SECONDS = 120

Confidence = Literal["fresh", "delayed", "stale", "disputed", "closed"]


@dataclass(frozen=True)
class Reconciled:
    price: float
    prev_close: float
    open: float
    day_high: float
    day_low: float
    volume: int
    as_of: datetime
    source: Literal["yahoo", "bse"]
    confidence: Confidence
    alt: dict | None
    divergence_pct: float | None
    staleness_seconds: int


def reconcile(
    primary: LiveQuote | None, alt: LiveQuote | None, now: datetime, market_status: str
) -> Reconciled | None:
    if primary is None and alt is None:
        return None
    divergence = _divergence_pct(primary, alt)
    disputed = divergence is not None and divergence > DISPUTE_THRESHOLD_PCT
    served, other = _pick_served(primary, alt, disputed)
    staleness = max(0, int((now - served.as_of).total_seconds()))
    return Reconciled(
        price=served.price,
        prev_close=served.prev_close,
        open=served.open,
        day_high=served.day_high,
        day_low=served.day_low,
        volume=served.volume,
        as_of=served.as_of,
        source=served.source,
        confidence=_confidence(market_status, disputed, primary is None, staleness),
        alt=_alt_view(other),
        divergence_pct=divergence,
        staleness_seconds=staleness,
    )


def _divergence_pct(primary: LiveQuote | None, alt: LiveQuote | None) -> float | None:
    if primary is None or alt is None:
        return None
    return round(abs(primary.price - alt.price) / primary.price * 100, 4)


def _pick_served(
    primary: LiveQuote | None, alt: LiveQuote | None, disputed: bool
) -> tuple[LiveQuote, LiveQuote | None]:
    if primary is None:
        return alt, None
    if disputed and alt.as_of > primary.as_of:
        return alt, primary
    return primary, alt


def _confidence(
    market_status: str, disputed: bool, primary_missing: bool, staleness: int
) -> Confidence:
    if market_status == "closed":
        return "closed"
    if disputed:
        return "disputed"
    if primary_missing:
        return "delayed"
    if staleness > STALE_AFTER_SECONDS:
        return "stale"
    return "fresh"


def _alt_view(other: LiveQuote | None) -> dict | None:
    if other is None:
        return None
    return {"price": other.price, "source": other.source, "as_of": other.as_of}
