from datetime import datetime, timedelta

from app.clock import IST
from app.providers.base import LiveQuote
from app.providers.reconcile import reconcile

NOW = datetime(2026, 9, 4, 10, 15, tzinfo=IST)


def quote(source: str, price: float, age_seconds: int) -> LiveQuote:
    return LiveQuote(
        symbol="RELIANCE.NS",
        price=price,
        prev_close=1302.5,
        day_high=price + 5,
        day_low=price - 5,
        volume=1000,
        as_of=NOW - timedelta(seconds=age_seconds),
        source=source,
    )


def test_agreement_is_fresh_with_alt_and_divergence():
    result = reconcile(quote("yahoo", 1326.80, 8), quote("bse", 1326.60, 900), NOW, "open")

    assert result.confidence == "fresh"
    assert result.source == "yahoo"
    assert result.price == 1326.80
    assert result.staleness_seconds == 8
    assert result.alt == {"price": 1326.60, "source": "bse", "as_of": NOW - timedelta(seconds=900)}
    assert result.divergence_pct == 0.0151


def test_divergence_over_threshold_is_disputed_and_serves_the_fresher():
    result = reconcile(quote("yahoo", 1300.0, 600), quote("bse", 1310.0, 30), NOW, "open")

    assert result.confidence == "disputed"
    assert result.source == "bse"
    assert result.price == 1310.0
    assert result.alt["source"] == "yahoo"
    assert result.alt["price"] == 1300.0
    assert result.divergence_pct > 0.5


def test_disputed_keeps_primary_when_primary_is_fresher():
    result = reconcile(quote("yahoo", 1300.0, 5), quote("bse", 1310.0, 900), NOW, "open")

    assert result.confidence == "disputed"
    assert result.source == "yahoo"
    assert result.alt["source"] == "bse"


def test_closed_market_is_closed_not_stale():
    result = reconcile(quote("yahoo", 1322.0, 3 * 3600), None, NOW, "closed")

    assert result.confidence == "closed"
    assert result.alt is None
    assert result.divergence_pct is None


def test_staleness_over_120_seconds_is_stale():
    assert reconcile(quote("yahoo", 1322.0, 121), None, NOW, "open").confidence == "stale"
    assert reconcile(quote("yahoo", 1322.0, 120), None, NOW, "open").confidence == "fresh"


def test_alt_only_is_delayed():
    result = reconcile(None, quote("bse", 1322.0, 900), NOW, "open")

    assert result.confidence == "delayed"
    assert result.source == "bse"
    assert result.alt is None
    assert result.divergence_pct is None
    assert result.staleness_seconds == 900


def test_both_missing_is_none():
    assert reconcile(None, None, NOW, "open") is None


def test_future_as_of_clamps_staleness_to_zero():
    assert reconcile(quote("yahoo", 1322.0, -30), None, NOW, "open").staleness_seconds == 0
