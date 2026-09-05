import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import auth, evidence, notifications, oauth, rules, symbols, watchlist
from app.api import health as health_api
from app.cache import cache
from app.config import settings
from app.deps import ApiError
from app.jobs.daily import ensure_seeded
from app.jobs.scheduler import start_scheduler, stop_scheduler
from app.schemas import ErrorBody, ErrorOut, HealthOut

log = logging.getLogger(__name__)

LOG_FORMAT = "ts=%(asctime)s level=%(levelname)s logger=%(name)s %(message)s"


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.DEBUG if settings.debug else logging.INFO,
        format=LOG_FORMAT,
        datefmt="%Y-%m-%dT%H:%M:%S%z",
        force=True,
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    log.info("startup cache_mode=%s cache_ok=%s", cache.mode, cache.ping())
    if not settings.replay_date:
        ensure_seeded()
    start_scheduler(app)
    yield
    stop_scheduler()
    log.info("shutdown")


def error_response(status: int, code: str, message: str, retry_after: int | None = None):
    body = ErrorOut(error=ErrorBody(code=code, message=message, retry_after_seconds=retry_after))
    return JSONResponse(status_code=status, content=body.model_dump(exclude_none=True))


async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    return error_response(exc.status, exc.code, exc.message, exc.retry_after_seconds)


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    log.exception("unhandled_error path=%s", request.url.path)
    return error_response(500, "internal_error", "internal error")


def health() -> HealthOut:
    return HealthOut(ok=True)


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(title="Smart Market Watchlist", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )
    app.add_exception_handler(ApiError, api_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)
    app.add_api_route("/api/health", health, methods=["GET"], response_model=HealthOut)
    for router in (
        auth.router,
        oauth.router,
        watchlist.router,
        symbols.router,
        rules.router,
        evidence.router,
        notifications.router,
        health_api.router,
    ):
        app.include_router(router, prefix="/api")
    return app
