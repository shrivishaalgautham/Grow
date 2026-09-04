from datetime import date, datetime, time, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import DailyBar

IST = ZoneInfo("Asia/Kolkata")
PRE_OPEN = time(9, 0)
OPEN = time(9, 15)
CLOSE = time(15, 30)
SESSION_MINUTES = 375

MarketStatus = Literal["open", "closed", "pre_open"]


def now() -> datetime:
    if settings.replay_date:
        return datetime.combine(settings.replay_date, CLOSE, tzinfo=IST)
    return datetime.now(IST)


def is_weekday(day: date) -> bool:
    return day.weekday() < 5


def market_status(at: datetime) -> MarketStatus:
    local = at.astimezone(IST)
    if not is_weekday(local.date()):
        return "closed"
    if PRE_OPEN <= local.time() < OPEN:
        return "pre_open"
    if OPEN <= local.time() < CLOSE:
        return "open"
    return "closed"


def minutes_since_open(at: datetime) -> int:
    local = at.astimezone(IST)
    opened = datetime.combine(local.date(), OPEN, tzinfo=IST)
    elapsed = int((local - opened).total_seconds() // 60)
    return max(0, min(SESSION_MINUTES, elapsed))


def trading_date(at: datetime) -> date:
    local = at.astimezone(IST)
    day = local.date()
    if local.time() < OPEN:
        day -= timedelta(days=1)
    while not is_weekday(day):
        day -= timedelta(days=1)
    return day


def latest_bar_date(session: Session) -> date | None:
    return session.execute(select(func.max(DailyBar.date))).scalar_one()
