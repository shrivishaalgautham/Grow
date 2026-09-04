import logging

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.ratelimit import global_ip_limit
from app.cache import cache
from app.config import settings
from app.db import get_session
from app.providers.ratelimit import CircuitBreaker
from app.schemas import ProvidersHealthOut, SchedulerHealth

log = logging.getLogger(__name__)

PROVIDERS = ("yahoo", "bse")
LAST_REFRESH_KEY = "scheduler:last_refresh_at"

router = APIRouter(prefix="/health", tags=["health"], dependencies=[Depends(global_ip_limit)])


@router.get("/providers", response_model=ProvidersHealthOut)
def providers(session: Session = Depends(get_session)) -> ProvidersHealthOut:
    return ProvidersHealthOut(
        providers=[CircuitBreaker(name).snapshot() for name in PROVIDERS],
        scheduler=SchedulerHealth(last_refresh_at=cache.get(LAST_REFRESH_KEY)),
        redis=_redis_status(),
        db=_db_status(session),
    )


def _redis_status() -> str:
    if cache.mode == "memory":
        return "down" if settings.redis_url else "disabled"
    return "ok" if cache.ping() else "down"


def _db_status(session: Session) -> str:
    try:
        session.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        log.warning("db_health_failed reason=%s", type(exc).__name__)
        return "down"
    return "ok"
