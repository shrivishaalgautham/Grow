import hashlib
import json
import logging
import re
from datetime import date, datetime

from sqlalchemy.orm import Session

from app.ai import client
from app.ai.prompts import BRIEFING_SYSTEM, UNTRUSTED_BEGIN, UNTRUSTED_END, untrusted
from app.deps import ApiError
from app.jobs import catalysts
from app.models import BriefingCache, User
from app.schemas import BriefingOut, DigestOut, Item

log = logging.getLogger(__name__)

MAX_CHARS = 600
MAX_TOKENS = 800
MAX_ITEMS = 5
MAX_CATALYSTS = 3
BANNED_WORDS = (
    "bullish",
    "bearish",
    "buy",
    "sell",
    "hold",
    "opportunity",
    "risk",
    "target",
)
NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")
URL_RE = re.compile(r"https?://|www\.|\]\(|@", re.IGNORECASE)
TICKER_RE = re.compile(r"\b[A-Z][A-Z&-]{2,}\b")
NOT_TICKERS = {"NSE", "BSE", "IST", "INR", "DMA", "AND", "THE", "NOT"}


def generate(session: Session, user: User, digest: DigestOut, now: datetime) -> BriefingOut:
    facts = facts_from_digest(digest)
    key = cache_key(user, digest)
    hit = session.get(BriefingCache, key)
    if hit is not None:
        return BriefingOut(
            text=hit.text, source=hit.source, generated_at=hit.generated_at, was_cached=True
        )
    text, source = _compose(user, facts)
    session.merge(
        BriefingCache(cache_key=key, user_id=user.id, text=text, source=source, generated_at=now)
    )
    session.commit()
    return BriefingOut(text=text, source=source, generated_at=now, was_cached=False)


def cache_key(user: User, digest: DigestOut) -> str:
    fired = sorted(
        (item.symbol, signal.type, signal.trading_date.isoformat(), signal.rule_id or "")
        for item in digest.items
        if item.is_changed
        for signal in item.signals
    )
    anchor = digest.last_reviewed_at.isoformat() if digest.last_reviewed_at else ""
    raw = json.dumps([str(user.id), anchor, digest.total_count, fired])
    return hashlib.sha256(raw.encode()).hexdigest()


def facts_from_digest(digest: DigestOut) -> dict:
    changed = [item for item in digest.items if item.is_changed][:MAX_ITEMS]
    statuses = catalysts.cached_statuses([i.symbol for i in changed], digest.latest_bar_date)
    return {
        "away_human": _away_human(digest.away_duration_seconds),
        "changed_count": digest.changed_count,
        "total_count": digest.total_count,
        "market_status": digest.market_status,
        "items": [item_facts(item, statuses.get(item.symbol)) for item in changed],
    }


def item_facts(item: Item, catalyst_status: str | None) -> dict:
    latest = max((s.trading_date for s in item.signals), default=None)
    found = catalysts.cached(item.symbol, latest) if latest else None
    headlines = [
        {
            "headline": untrusted(c.headline),
            "source": c.source,
            "published_at": c.published_at.isoformat() if c.published_at else None,
        }
        for c in (found.items if found else [])[:MAX_CATALYSTS]
    ]
    return {
        "symbol": item.symbol.split(".")[0],
        "today_change_pct": round(item.today_change_pct, 1),
        "peer_change_pct": round(item.peer_change_pct, 1),
        "residual_pct": round(item.residual_pct, 1),
        "z_score": round(item.z_score, 1),
        "rvol": round(item.rvol, 1),
        "peer_method": item.peer.method,
        "peer_size": item.peer.size,
        "signals": [
            {
                "type": s.type,
                "trading_date": s.trading_date.isoformat(),
                "headline": s.headline,
                "detail": s.detail,
            }
            for s in item.signals
        ],
        "catalyst_status": catalyst_status or "not_fetched",
        "catalysts": headlines,
    }


def _compose(user: User, facts: dict) -> tuple[str, str]:
    fallback = template(facts)
    if not client.is_configured() or not facts["items"]:
        return fallback, "template"
    if not _budget_allows(user):
        return fallback, "template"
    completion = client.complete(
        "briefing", BRIEFING_SYSTEM, json.dumps(facts, ensure_ascii=False), MAX_TOKENS
    )
    if completion is None:
        return fallback, "template"
    rejection = validate(completion.text, facts)
    if rejection is not None:
        log.info("briefing rejected model=%s reason=%s", completion.model, rejection)
        return fallback, "template"
    return completion.text, "llm"


def _budget_allows(user: User) -> bool:
    from app.api.ratelimit import llm_budget

    try:
        llm_budget(user)
    except ApiError as exc:
        log.info("briefing budget_exhausted scope=%s", exc.message)
        return False
    return True


def validate(text: str, facts: dict) -> str | None:
    if len(text) > MAX_CHARS:
        return "too_long"
    if URL_RE.search(text):
        return "url_or_markup"
    lowered = text.lower()
    for word in BANNED_WORDS:
        if re.search(rf"\b{word}\b", lowered):
            return f"banned_word:{word}"
    allowed_numbers = {abs(float(n)) for n in NUMBER_RE.findall(_numeric_source(facts))}
    for token in NUMBER_RE.findall(text):
        if abs(float(token)) not in allowed_numbers:
            return f"foreign_number:{token}"
    for token in TICKER_RE.findall(text):
        if token not in _allowed_symbols(facts) and token not in NOT_TICKERS:
            return f"foreign_symbol:{token}"
    return None


def _allowed_symbols(facts: dict) -> set[str]:
    return {item["symbol"] for item in facts["items"]} | {
        word
        for item in facts["items"]
        for signal in item["signals"]
        for word in TICKER_RE.findall(signal["type"])
    }


def _numeric_source(facts: dict) -> str:
    stripped = {
        **facts,
        "items": [{k: v for k, v in item.items() if k != "catalysts"} for item in facts["items"]],
    }
    return json.dumps(stripped)


def template(facts: dict) -> str:
    changed, total = facts["changed_count"], facts["total_count"]
    away = facts["away_human"]
    if total == 0:
        return "Your watchlist is empty, so there is nothing to report yet."
    if changed == 0 or not facts["items"]:
        return (
            f"You were away {away}. Nothing among your {total} stocks needed attention; "
            "every move stayed inside what the market and its peers explain."
        )
    top = facts["items"][0]
    return (
        f"You were away {away}. {changed} of {total} stocks did something meaningful. "
        f"The one to look at is {top['symbol']}: {_top_event(top)}{_catalyst_clause(top)}."
    )


def _top_event(item: dict) -> str:
    excess = [s for s in item["signals"] if s["type"] == "EXCESS_MOVE"]
    signal = (excess or item["signals"])[0]
    when = date.fromisoformat(signal["trading_date"]).strftime("%-d %b")
    return f"{signal['detail'].rstrip('.')} ({signal['headline'].lower()}, {when})"


def _catalyst_clause(item: dict) -> str:
    if item["catalyst_status"] == "none_found":
        return ", with no public catalyst found"
    if item["catalyst_status"] == "found" and item["catalysts"]:
        headline = item["catalysts"][0]["headline"]
        quoted = headline.removeprefix(UNTRUSTED_BEGIN).removesuffix(UNTRUSTED_END)
        return f", coinciding with: {quoted}"
    return ""


def _away_human(seconds: int | None) -> str:
    if seconds is None:
        return "for the first time"
    days = seconds // 86400
    if days >= 1:
        return f"{days} day{'s' if days != 1 else ''}"
    hours = seconds // 3600
    if hours >= 1:
        return f"{hours} hour{'s' if hours != 1 else ''}"
    return "less than an hour"
