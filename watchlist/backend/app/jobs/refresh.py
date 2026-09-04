import json
import logging
import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app import clock, db
from app.cache import cache
from app.config import settings
from app.engine.baselines import Baseline
from app.engine.peers import peer_return
from app.engine.signals import SessionFacts, evaluate
from app.jobs import store
from app.models import Baseline as BaselineRow
from app.providers.base import INDEX_SYMBOL, LiveQuote, ProviderError
from app.providers.bse import SCRIP_CODES, Bse
from app.providers.ratelimit import CircuitBreaker
from app.providers.reconcile import Reconciled, reconcile
from app.providers.yahoo import Yahoo

log = logging.getLogger(__name__)

WARM_SECONDS = 300
WARM_BATCH = 60
FAIL_TTL_S = 1800
SKIP_AFTER_FAILURES = 3
QUOTE_TTL_S = 600
HEARTBEAT_TTL_S = 3600
CURSOR_TTL_S = 86400

_yahoo = Yahoo()
_bse = Bse()


@dataclass(frozen=True)
class RefreshSummary:
    symbols: int
    fetched: int
    disputed: int
    signals_inserted: int
    skipped: int
    ms: int


def refresh_tick(now: datetime) -> RefreshSummary:
    started = time.monotonic()
    commands_before = cache.commands_issued
    with db.SessionLocal() as session:
        active = store.active_symbols(session)
        watched = store.watched_symbols(session)
    symbols = _select_symbols(now, active, watched)
    fetchable, skipped = _without_skipped(symbols)
    quotes = _fetch_quotes(fetchable, now)
    rows = {symbol: _quote_row(symbol, quote, now) for symbol, quote in quotes.items()}
    with db.SessionLocal() as session:
        signals = _signal_rows(session, quotes, now)
        store.upsert_quotes(session, list(rows.values()))
        inserted = store.insert_signal_events(session, signals)
        session.commit()
    _publish(rows, quotes, now)
    summary = RefreshSummary(
        symbols=len(symbols),
        fetched=len(quotes),
        disputed=sum(quote.confidence == "disputed" for quote in quotes.values()),
        signals_inserted=inserted,
        skipped=len(skipped),
        ms=int((time.monotonic() - started) * 1000),
    )
    log.info(
        "refresh symbols=%d fetched=%d disputed=%d signals_inserted=%d skipped=%d ms=%d "
        "cache_commands=%d",
        summary.symbols,
        summary.fetched,
        summary.disputed,
        summary.signals_inserted,
        summary.skipped,
        summary.ms,
        cache.commands_issued - commands_before,
    )
    return summary


def _select_symbols(now: datetime, active: Sequence[str], watched: Sequence[str]) -> list[str]:
    hot = set(watched) | {INDEX_SYMBOL} | _requested(active)
    if _is_warm_tick(now):
        hot |= _warm_batch([symbol for symbol in active if symbol not in hot])
    return sorted(hot)


def _requested(active: Sequence[str]) -> set[str]:
    keys = [f"refresh:req:{symbol}" for symbol in active]
    found = {symbol for symbol, flag in zip(active, cache.mget(keys), strict=True) if flag}
    for symbol in found:
        cache.delete(f"refresh:req:{symbol}")
    return found


def _is_warm_tick(now: datetime) -> bool:
    return now.timestamp() % WARM_SECONDS < settings.refresh_hot_seconds


def _warm_batch(candidates: list[str]) -> set[str]:
    if not candidates:
        return set()
    cursor = int(cache.get("refresh:warm_cursor") or 0) % len(candidates)
    rotated = candidates[cursor:] + candidates[:cursor]
    next_cursor = (cursor + WARM_BATCH) % len(candidates)
    cache.set_many({"refresh:warm_cursor": str(next_cursor)}, ttl=CURSOR_TTL_S)
    return set(rotated[:WARM_BATCH])


def _without_skipped(symbols: list[str]) -> tuple[list[str], list[str]]:
    flags = cache.mget([f"skip:{symbol}" for symbol in symbols])
    skipped = [symbol for symbol, flag in zip(symbols, flags, strict=True) if flag]
    return [symbol for symbol in symbols if symbol not in skipped], skipped


def _fetch_quotes(symbols: list[str], now: datetime) -> dict[str, Reconciled]:
    primaries = _yahoo_quotes(symbols)
    alts = _bse_quotes(symbols)
    status = clock.market_status(now)
    reconciled = {
        symbol: reconcile(primaries.get(symbol), alts.get(symbol), now, status)
        for symbol in symbols
    }
    return {symbol: quote for symbol, quote in reconciled.items() if quote is not None}


def _yahoo_quotes(symbols: list[str]) -> dict[str, LiveQuote]:
    breaker = CircuitBreaker("yahoo")
    found: dict[str, LiveQuote] = {}
    for position, symbol in enumerate(symbols):
        quote = _yahoo_quote(symbol)
        if quote is not None:
            found[symbol] = quote
            continue
        if not breaker.allow():
            log.warning("refresh provider=yahoo circuit_open unfetched=%d", len(symbols) - position)
            break
        _record_failure(symbol)
    _clear_failures(list(found))
    return found


def _yahoo_quote(symbol: str) -> LiveQuote | None:
    try:
        return _yahoo.quotes([symbol]).get(symbol)
    except ProviderError as exc:
        log.warning("refresh symbol=%s provider=yahoo error=%s", symbol, exc)
        return None


def _record_failure(symbol: str) -> None:
    failures = cache.incr(f"fail:{symbol}", FAIL_TTL_S)
    if failures >= SKIP_AFTER_FAILURES:
        cache.set_many({f"skip:{symbol}": "1"}, ttl=FAIL_TTL_S)
        log.warning("refresh symbol=%s skipped_for=%ds failures=%d", symbol, FAIL_TTL_S, failures)


def _clear_failures(symbols: list[str]) -> None:
    if not symbols:
        return
    keys = [f"fail:{symbol}" for symbol in symbols]
    for key, count in zip(keys, cache.mget(keys), strict=True):
        if count is not None:
            cache.delete(key)


def _bse_quotes(symbols: list[str]) -> dict[str, LiveQuote]:
    found: dict[str, LiveQuote] = {}
    for symbol in symbols:
        if symbol.removesuffix(".NS") not in SCRIP_CODES:
            continue
        try:
            found.update(_bse.quotes([symbol]))
        except ProviderError as exc:
            log.warning("refresh symbol=%s provider=bse error=%s", symbol, exc)
    return found


def _quote_row(symbol: str, quote: Reconciled, now: datetime) -> dict:
    return store.quote_row(
        symbol,
        price=quote.price,
        prev_close=quote.prev_close,
        day_high=quote.day_high,
        day_low=quote.day_low,
        volume=quote.volume,
        as_of=quote.as_of,
        source=quote.source,
        confidence=quote.confidence,
        updated_at=now,
        alt=quote.alt,
        divergence_pct=quote.divergence_pct,
    )


def _signal_rows(session: Session, quotes: dict[str, Reconciled], now: datetime) -> list[dict]:
    baselines = store.load_baselines(session, list(quotes))
    members = store.cluster_members(session)
    peers = {s for b in baselines.values() if b.cluster_id for s in members[b.cluster_id]}
    returns_today = _returns_today(quotes, [INDEX_SYMBOL, *peers], clock.trading_date(now))
    index_return = returns_today.get(INDEX_SYMBOL)
    if index_return is None:
        log.warning("refresh index_return=missing signals=skipped")
        return []
    rows: list[dict] = []
    for symbol, quote in quotes.items():
        baseline = baselines.get(symbol)
        if baseline is None or quote.confidence == "disputed" or quote.prev_close <= 0:
            continue
        peer = None
        if baseline.cluster_id:
            peer = peer_return(returns_today, members[baseline.cluster_id], exclude=symbol)
        facts = _facts(symbol, quote, index_return, peer, baseline.cluster_id, now)
        rows.extend(store.signal_rows(facts, evaluate(facts, _engine_baseline(baseline))))
    return rows


def _returns_today(
    quotes: dict[str, Reconciled], extra: Sequence[str], trading_date
) -> dict[str, float]:
    returns = {s: q.price / q.prev_close - 1 for s, q in quotes.items() if q.prev_close > 0}
    missing = sorted(set(extra) - set(returns))
    if not missing:
        return returns
    for symbol, raw in zip(missing, cache.mget([f"q:{s}" for s in missing]), strict=True):
        if raw is None:
            continue
        cached = json.loads(raw)
        is_today = datetime.fromisoformat(cached["as_of"]).date() == trading_date
        if is_today and cached["prev_close"] > 0:
            returns[symbol] = cached["price"] / cached["prev_close"] - 1
    return returns


def _facts(
    symbol: str,
    quote: Reconciled,
    index_return: float,
    peer: float | None,
    cluster_id: str | None,
    now: datetime,
) -> SessionFacts:
    is_open = clock.market_status(now) == "open"
    return SessionFacts(
        symbol=symbol,
        price=quote.price,
        prev_close=quote.prev_close,
        day_high=quote.day_high,
        day_low=quote.day_low,
        volume=float(quote.volume),
        index_return=index_return,
        peer_return=peer,
        peer_cluster_id=cluster_id,
        minutes_since_open=clock.minutes_since_open(now) if is_open else None,
        trading_date=clock.trading_date(now),
        fired_at=now,
    )


def _engine_baseline(row: BaselineRow) -> Baseline:
    return Baseline(
        beta=row.beta,
        residual_sigma=row.residual_sigma,
        raw_mean_20=row.raw_mean_20,
        raw_sigma_20=row.raw_sigma_20,
        sigma_daily_90=row.sigma_daily_90,
        avg_volume_20d=row.avg_volume_20d,
        sma_20=row.sma_20,
        sma_50=row.sma_50,
        sma_200=row.sma_200,
        high_52w=row.high_52w,
        low_52w=row.low_52w,
        prev_close=row.prev_close,
        prev_high=row.prev_high,
        prev_low=row.prev_low,
        confidence=row.confidence,
        sessions=0,
    )


def _publish(rows: dict[str, dict], quotes: dict[str, Reconciled], now: datetime) -> None:
    if rows:
        cache.set_many(
            {
                f"q:{symbol}": json.dumps(
                    store.quote_cache_value(row, quotes[symbol].staleness_seconds)
                )
                for symbol, row in rows.items()
            },
            ttl=QUOTE_TTL_S,
        )
    cache.set_many({"scheduler:last_refresh_at": now.isoformat()}, ttl=HEARTBEAT_TTL_S)
