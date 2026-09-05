import json
import logging
from datetime import date, datetime

from app.ai import client
from app.ai.briefing import item_facts, validate
from app.ai.prompts import EXPLAIN_SYSTEM
from app.api.ratelimit import llm_budget
from app.cache import cache
from app.deps import ApiError
from app.models import User
from app.schemas import CatalystsOut, ExplanationOut, Item

log = logging.getLogger(__name__)

CACHE_TTL_S = 1200
MAX_TOKENS = 700
MAX_HEADLINES = 3


def cache_key(symbol: str, trading_date: date) -> str:
    return f"explain:{symbol}:{trading_date.isoformat()}"


def explain(
    user: User, item: Item, catalysts: CatalystsOut, trading_date: date, now: datetime
) -> ExplanationOut:
    key = cache_key(item.symbol, trading_date)
    hit = cache.get(key)
    if hit:
        cached = ExplanationOut.model_validate_json(hit)
        return cached.model_copy(update={"was_cached": True})
    facts = {"items": [item_facts(item, catalysts.status)]}
    text, source = _compose(user, facts)
    result = ExplanationOut(
        status="ready",
        text=text,
        source=source,
        catalyst_status=catalysts.status,
        items=catalysts.items[:MAX_HEADLINES],
        generated_at=now,
        was_cached=False,
    )
    cache.set_many({key: result.model_dump_json()}, ttl=CACHE_TTL_S)
    return result


def _compose(user: User, facts: dict) -> tuple[str, str]:
    fallback = template(facts["items"][0])
    if not client.is_configured() or not _budget_allows(user):
        return fallback, "template"
    completion = client.complete(
        "explain", EXPLAIN_SYSTEM, json.dumps(facts, ensure_ascii=False), MAX_TOKENS
    )
    if completion is None:
        return fallback, "template"
    rejection = validate(completion.text, facts)
    if rejection is not None:
        log.info("explain rejected model=%s reason=%s", completion.model, rejection)
        return fallback, "template"
    return completion.text, "llm"


def _budget_allows(user: User) -> bool:
    try:
        llm_budget(user)
    except ApiError:
        return False
    return True


def template(item: dict) -> str:
    symbol = item["symbol"]
    signals = "; ".join(dict.fromkeys(s["headline"].lower() for s in item["signals"]))
    sentence = (
        f"{symbol} moved {item['today_change_pct']:+.1f}% while its peer group moved "
        f"{item['peer_change_pct']:+.1f}%, leaving {item['residual_pct']:+.1f}% that is "
        f"stock-specific"
    )
    if signals:
        sentence += f" ({signals})"
    sentence += "."
    return f"{sentence} {_catalyst_sentence(item)}".strip()


def _catalyst_sentence(item: dict) -> str:
    status = item["catalyst_status"]
    if status == "none_found":
        return "No public catalyst was found in the last three days of filings and headlines."
    if status == "unavailable":
        return "The news sources could not be checked, so the absence of a headline means nothing."
    if status == "found" and item["catalysts"]:
        quoted = "; ".join(
            f"“{_strip(c['headline'])}” ({c['source']})" for c in item["catalysts"][:2]
        )
        return f"Recent headlines the move coincided with: {quoted}."
    return ""


def _strip(headline: str) -> str:
    return headline.replace("<<UNTRUSTED>>", "").replace("<</UNTRUSTED>>", "")
