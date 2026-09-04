import hashlib
import logging
import re
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app import clock
from app.ai import client
from app.ai.prompts import BriefingFacts, SymbolFacts, briefing_messages
from app.jobs.catalysts import cached_catalysts
from app.models import BriefingCache, Symbol, User
from app.schemas import BriefingOut, DigestOut, Item

log = logging.getLogger(__name__)

MAX_CHARS = 600
MAX_TOKENS = 300
MAX_NAMED = 3
CACHE_TTL = timedelta(hours=6)
DAY_SECONDS = 86400

URL_RE = re.compile(r"https?://|www\.", re.IGNORECASE)
MARKDOWN_LINK_RE = re.compile(r"\[[^\]]*\]\([^)]*\)")
BANNED_RE = re.compile(
    r"\b(ignore|disregard|instructions?|system prompt|buy|sell(?!-off)|hold|recommend|"
    r"should|must|guaranteed?)\b",
    re.IGNORECASE,
)
SYMBOL_TOKEN_RE = re.compile(r"\b[A-Z][A-Z0-9&-]{0,18}[A-Z0-9](?:\.NS|\.BO)?")


def briefing_facts(digest: DigestOut, now: datetime) -> BriefingFacts:
    away = digest.away_duration_seconds
    return BriefingFacts(
        latest_bar_date=digest.latest_bar_date,
        total_count=digest.total_count,
        changed=tuple(_symbol_facts(item, now) for item in digest.items if item.is_changed),
        away_days=None if away is None else away // DAY_SECONDS,
    )


def cached_briefing(
    session: Session, user: User, facts: BriefingFacts, now: datetime
) -> BriefingOut | None:
    row = session.get(BriefingCache, _cache_key(user, facts))
    if row is None or now - row.generated_at >= CACHE_TTL:
        return None
    return BriefingOut(
        text=row.text,
        source=row.source,
        generated_at=row.generated_at.astimezone(clock.IST),
        was_cached=True,
    )


def generate_briefing(
    session: Session, user: User, facts: BriefingFacts, now: datetime
) -> BriefingOut:
    text, source = _compose(session, facts)
    _store(session, user, _cache_key(user, facts), text, source, now)
    session.commit()
    log.info("briefing source=%s changed=%d chars=%d", source, len(facts.changed), len(text))
    return BriefingOut(text=text, source=source, generated_at=now, was_cached=False)


def rejection_reason(text: str, facts: BriefingFacts, universe: set[str]) -> str | None:
    if not text:
        return "empty"
    if len(text) > MAX_CHARS:
        return "too_long"
    if URL_RE.search(text):
        return "url"
    if "@" in text:
        return "mention"
    if MARKDOWN_LINK_RE.search(text):
        return "markdown_link"
    if BANNED_RE.search(text):
        return "banned_word"
    if _foreign_symbols(text, facts, universe):
        return "foreign_symbol"
    return None


def template(facts: BriefingFacts) -> str:
    for named in range(MAX_NAMED, 0, -1):
        text = _template(facts, named)
        if len(text) <= MAX_CHARS:
            return text
    return _template(facts, 0)


def _symbol_facts(item: Item, now: datetime) -> SymbolFacts:
    catalysts = cached_catalysts(item.symbol, now)
    return SymbolFacts(
        symbol=item.symbol,
        today_change_pct=item.today_change_pct,
        peer_change_pct=item.peer_change_pct,
        residual_pct=item.residual_pct,
        z_score=item.z_score,
        rvol=item.rvol,
        headlines=tuple(c.headline for c in catalysts.items) if catalysts else (),
    )


def _cache_key(user: User, facts: BriefingFacts) -> str:
    owner = "sample" if user.is_sample else str(user.id)
    state = "|".join([facts.latest_bar_date.isoformat(), *sorted(s.symbol for s in facts.changed)])
    return f"{owner}:{hashlib.sha256(state.encode()).hexdigest()[:32]}"


def _compose(session: Session, facts: BriefingFacts) -> tuple[str, str]:
    raw = client.complete(briefing_messages(facts), MAX_TOKENS)
    if raw is None:
        return template(facts), "template"
    reason = rejection_reason(raw, facts, _universe(session))
    if reason is not None:
        log.info("briefing_rejected reason=%s chars=%d", reason, len(raw))
        return template(facts), "template"
    return raw, "llm"


def _universe(session: Session) -> set[str]:
    return set(session.scalars(select(Symbol.symbol)))


def _foreign_symbols(text: str, facts: BriefingFacts, universe: set[str]) -> set[str]:
    allowed = {_base(item.symbol) for item in facts.changed}
    mentioned = {_base(token) for token in SYMBOL_TOKEN_RE.findall(text)}
    known = {_base(symbol) for symbol in universe}
    return (mentioned & known) - allowed


def _base(symbol: str) -> str:
    return symbol.rpartition(".")[0] if symbol.endswith((".NS", ".BO")) else symbol


def _store(session: Session, user: User, key: str, text: str, source: str, now: datetime) -> None:
    statement = insert(BriefingCache).values(
        cache_key=key, user_id=user.id, text=text, source=source, generated_at=now
    )
    session.execute(
        statement.on_conflict_do_update(
            index_elements=["cache_key"],
            set_={
                "user_id": statement.excluded.user_id,
                "text": statement.excluded.text,
                "source": statement.excluded.source,
                "generated_at": statement.excluded.generated_at,
            },
        )
    )


def _template(facts: BriefingFacts, named: int) -> str:
    if facts.total_count == 0:
        return "Your watchlist is empty, so there is nothing to brief on yet. Add a few stocks."
    window = "since your last review" if facts.away_days is None else _away_phrase(facts.away_days)
    if not facts.changed:
        return (
            f"None of your {facts.total_count} watched stocks moved on its own {window}; "
            "they all tracked their peers."
        )
    sentences = [
        f"{len(facts.changed)} of {facts.total_count} watched stocks moved on their own {window}."
    ]
    sentences.extend(_describe(item) for item in facts.changed[:named])
    unnamed = len(facts.changed) - named
    if unnamed > 0:
        sentences.append(f"{unnamed} more also moved.")
    if facts.quiet_count > 0:
        sentences.append(f"The other {facts.quiet_count} were quiet.")
    return " ".join(sentences)


def _away_phrase(days: int) -> str:
    if days < 1:
        return "since your last review earlier today"
    return f"in the {days} {'day' if days == 1 else 'days'} since your last review"


def _describe(item: SymbolFacts) -> str:
    direction = "rose" if item.today_change_pct >= 0 else "fell"
    text = (
        f"{_base(item.symbol)} {direction} {abs(item.today_change_pct):.1f}% against "
        f"{item.peer_change_pct:+.1f}% for its peers, a {item.z_score:.1f}-sigma stock-specific "
        f"move on {item.rvol:.1f}x normal volume."
    )
    if item.headlines:
        text += " A public headline was found."
    return text
