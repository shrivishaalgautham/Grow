import math
from dataclasses import dataclass
from datetime import date, datetime

from app.engine.baselines import Baseline
from app.engine.levels import level_breaks
from app.engine.residual import Decomposition, decompose
from app.engine.score import attention, score
from app.engine.volume import relative_volume
from app.schemas import Signal

EXCESS_FLOOR_PCT = 0.75
EXCESS_Z = 2.0
RVOL_CONFIRM = 1.5
UNUSUAL_Z = 3.0
SINCE_SEEN_Z = 2.0
SINCE_SEEN_FLOOR_PCT = 1.5

LEVEL_HEADLINES = {
    "52w_high": "New 52-week high",
    "52w_low": "New 52-week low",
    "prev_high": "Above yesterday's high",
    "prev_low": "Below yesterday's low",
}


@dataclass(frozen=True)
class SessionFacts:
    symbol: str
    price: float
    prev_close: float
    day_high: float
    day_low: float
    volume: float
    index_return: float
    peer_return: float | None
    peer_cluster_id: str | None
    minutes_since_open: int | None
    trading_date: date
    fired_at: datetime


@dataclass(frozen=True)
class Evaluation:
    decomposition: Decomposition
    rvol: float
    rvol_is_approximate: bool
    breaks: list[str]
    signals: list[Signal]
    score: float
    attention: str
    is_changed: bool
    low_confidence: bool


def evaluate(facts: SessionFacts, b: Baseline) -> Evaluation:
    decomposition = decompose(
        facts.price, facts.prev_close, facts.index_return, facts.peer_return, b
    )
    rvol, is_approximate = relative_volume(facts.volume, b.avg_volume_20d, facts.minutes_since_open)
    breaks = level_breaks(facts.price, facts.day_high, facts.day_low, b)
    is_low_confidence = b.confidence == "low"
    signals = (
        []
        if is_low_confidence
        else _fired_signals(facts, b, decomposition, rvol, is_approximate, breaks)
    )
    score_value = 0.0 if is_low_confidence else score(decomposition.z_score, rvol, breaks)
    return Evaluation(
        decomposition=decomposition,
        rvol=rvol,
        rvol_is_approximate=is_approximate,
        breaks=breaks,
        signals=signals,
        score=score_value,
        attention=attention(score_value, bool(signals)),
        is_changed=bool(signals),
        low_confidence=is_low_confidence,
    )


def _fired_signals(
    facts: SessionFacts,
    b: Baseline,
    d: Decomposition,
    rvol: float,
    rvol_is_approximate: bool,
    breaks: list[str],
) -> list[Signal]:
    signals: list[Signal] = []
    if abs(d.residual_pct) >= EXCESS_FLOOR_PCT and d.z_score >= EXCESS_Z:
        signals.append(_excess_move(facts, d))
    is_anchored = bool(signals) or any(_is_year_level(name) for name in breaks)
    if is_anchored and rvol >= RVOL_CONFIRM:
        signals.append(_volume_confirmed(facts, rvol, rvol_is_approximate))
    signals.extend(
        _level_break(facts, b, name) for name in breaks if is_anchored or _is_year_level(name)
    )
    return signals


def _is_year_level(name: str) -> bool:
    return name.startswith("52w_")


def _excess_move(facts: SessionFacts, d: Decomposition) -> Signal:
    headline = (
        "Unusually large stock-specific move"
        if d.z_score >= UNUSUAL_Z
        else "Notable stock-specific move"
    )
    if d.peer_method == "cluster":
        context = f"while its peer group averaged {_signed_pct(d.peer_change_pct)}"
    else:
        context = f"while the market moved {_signed_pct(d.peer_change_pct)}, beta-adjusted"
    detail = f"{_direction_pct(d.today_change_pct)} {context}."
    if d.raw_z_score >= EXCESS_Z:
        detail += " Also the largest daily move vs its own 20-day range."
    return _signal("EXCESS_MOVE", headline, detail, facts)


def _volume_confirmed(facts: SessionFacts, rvol: float, is_approximate: bool) -> Signal:
    detail = "Adjusted for time of day." if is_approximate else "Versus the 20-day median."
    return _signal("VOLUME_CONFIRMED", f"{rvol:.1f}× normal volume", detail, facts)


def _level_break(facts: SessionFacts, b: Baseline, name: str) -> Signal:
    if name == "52w_high":
        detail = f"Traded up to {facts.day_high:.2f}, above the 52-week high of {b.high_52w:.2f}."
    elif name == "52w_low":
        detail = f"Traded down to {facts.day_low:.2f}, below the 52-week low of {b.low_52w:.2f}."
    elif name == "prev_high":
        detail = f"Traded up to {facts.day_high:.2f}, above yesterday's high of {b.prev_high:.2f}."
    else:
        detail = f"Traded down to {facts.day_low:.2f}, below yesterday's low of {b.prev_low:.2f}."
    return _signal("LEVEL_BREAK", LEVEL_HEADLINES[name], detail, facts)


def _signal(type_: str, headline: str, detail: str, facts: SessionFacts) -> Signal:
    return Signal(
        type=type_,
        headline=headline,
        detail=detail,
        fired_at=facts.fired_at,
        trading_date=facts.trading_date,
        rule_id=None,
    )


def since_seen_signal(
    change_since_seen_pct: float,
    sigma_daily_90: float,
    trading_days_away: int,
    fired_at: datetime,
    trading_date: date,
) -> Signal | None:
    if sigma_daily_90 <= 0:
        return None
    days = max(trading_days_away, 1)
    expected_drift_pct = sigma_daily_90 * 100 * math.sqrt(days)
    magnitude = abs(change_since_seen_pct)
    if magnitude < SINCE_SEEN_FLOOR_PCT or magnitude / expected_drift_pct < SINCE_SEEN_Z:
        return None
    unit = "trading day" if days == 1 else "trading days"
    return Signal(
        type="SINCE_SEEN_MOVE",
        headline=f"{_signed_pct(change_since_seen_pct)} since you last checked",
        detail=f"Larger than expected drift over {days} {unit}.",
        fired_at=fired_at,
        trading_date=trading_date,
        rule_id=None,
    )


def _signed_pct(value: float) -> str:
    return f"{value:+.1f}%"


def _direction_pct(value: float) -> str:
    return f"{'Up' if value >= 0 else 'Down'} {abs(value):.1f}%"
