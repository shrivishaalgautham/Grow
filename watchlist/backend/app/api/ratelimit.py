from datetime import datetime, time, timedelta

from fastapi import Depends

from app import clock
from app.cache import cache
from app.config import settings
from app.deps import ApiError, current_user, enforce_window, rate_limit
from app.models import User

DAY_SECONDS = 86400
LLM_HOURLY_LIMIT = 5
LLM_DAILY_LIMIT = 20

global_ip_limit = rate_limit("global", 30, 60, per="ip")


def enforce_llm_budget(user: User) -> None:
    enforce_window("llm_hour", LLM_HOURLY_LIMIT, 3600, str(user.id))
    enforce_window("llm_day", LLM_DAILY_LIMIT, DAY_SECONDS, str(user.id))
    llm_global_daily()


def llm_budget(user: User = Depends(current_user)) -> None:
    enforce_llm_budget(user)


def llm_global_daily() -> None:
    now = clock.now()
    count = cache.incr(f"llm:{now:%Y-%m-%d}", DAY_SECONDS)
    if count <= settings.llm_global_daily_cap:
        return
    raise ApiError(
        429,
        "rate_limited",
        "daily assistant budget exhausted",
        retry_after_seconds=_seconds_until_midnight(now),
    )


def _seconds_until_midnight(now: datetime) -> int:
    local = now.astimezone(clock.IST)
    midnight = datetime.combine(local.date() + timedelta(days=1), time.min, tzinfo=clock.IST)
    return max(1, int((midnight - local).total_seconds()))
