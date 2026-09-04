from datetime import datetime, time, timedelta

from app import clock
from app.cache import cache
from app.config import settings
from app.deps import ApiError, rate_limit

DAY_SECONDS = 86400

global_ip_limit = rate_limit("global", 30, 60, per="ip")

llm_user_limits = (
    rate_limit("llm_hour", 5, 3600, per="user"),
    rate_limit("llm_day", 20, DAY_SECONDS, per="user"),
)


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
