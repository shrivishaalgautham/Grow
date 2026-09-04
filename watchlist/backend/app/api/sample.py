import secrets
import string
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import clock
from app.models import Symbol, User, WatchlistItem

DEMO_SYMBOLS = [
    "RELIANCE",
    "TCS",
    "INFY",
    "HDFCBANK",
    "ICICIBANK",
    "TMPV",
    "MARUTI",
    "SUNPHARMA",
    "ITC",
    "LT",
    "BHARTIARTL",
    "ADANIENT",
]
BACKDATE_DAYS = 7
NAME_ALPHABET = string.ascii_lowercase + string.digits


def sample_display_name() -> str:
    return "sample-" + "".join(secrets.choice(NAME_ALPHABET) for _ in range(4))


def seed_sample_watchlist(session: Session, user: User, now: datetime) -> list[str]:
    wanted = [f"{name}.NS" for name in DEMO_SYMBOLS]
    present = session.scalars(select(Symbol.symbol).where(Symbol.symbol.in_(wanted))).all()
    session.add_all(WatchlistItem(user_id=user.id, symbol=symbol) for symbol in present)
    user.is_sample = True
    user.last_reviewed_at = _review_anchor(session, now) - timedelta(days=BACKDATE_DAYS)
    return list(present)


def _review_anchor(session: Session, now: datetime) -> datetime:
    latest = clock.latest_bar_date(session)
    if latest is None:
        return now
    return datetime.combine(latest, clock.CLOSE, tzinfo=clock.IST)
