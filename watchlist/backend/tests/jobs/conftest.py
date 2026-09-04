import uuid
from datetime import datetime
from pathlib import Path

import httpx
import numpy as np
import pandas as pd
import pytest
import respx
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from alembic import command
from app import clock, db
from app.cache import cache
from app.config import settings
from app.jobs import store
from app.models import User, WatchlistItem
from app.providers.base import INDEX_SYMBOL, Bar
from app.providers.ratelimit import TokenBucket
from tests.synthetic import bars_from_returns

BACKEND = Path(__file__).resolve().parent.parent.parent
MAINTENANCE_URL = "postgresql+psycopg://watchlist:watchlist@localhost:5432/watchlist"
TEST_DB = "watchlist_test_jobs"
TEST_URL = f"postgresql+psycopg://watchlist:watchlist@localhost:5432/{TEST_DB}"
YAHOO_HOST = "query1.finance.yahoo.com"
BSE_HOST = "api.bseindia.com"
SESSIONS = 300
CORRELATED = ["A.NS", "B.NS", "C.NS", "D.NS"]
INDEPENDENT = ["E.NS", "F.NS"]
SYMBOLS = CORRELATED + INDEPENDENT
SHOCK_SYMBOL = "A.NS"
SHOCK_RETURN = 0.05


@pytest.fixture(scope="session")
def jobs_engine():
    _recreate_database()
    original_url = settings.database_url
    settings.database_url = TEST_URL
    try:
        command.upgrade(_alembic_config(), "head")
    finally:
        settings.database_url = original_url
    engine = create_engine(TEST_URL)
    yield engine
    engine.dispose()


def _recreate_database() -> None:
    admin = create_engine(MAINTENANCE_URL, isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.execute(text(f"DROP DATABASE IF EXISTS {TEST_DB}"))
        connection.execute(text(f"CREATE DATABASE {TEST_DB}"))
    admin.dispose()


def _alembic_config() -> Config:
    config = Config(str(BACKEND / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND / "alembic"))
    return config


@pytest.fixture
def session(jobs_engine, monkeypatch):
    connection = jobs_engine.connect()
    outer = connection.begin()
    factory = sessionmaker(
        bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
    )
    monkeypatch.setattr(db, "SessionLocal", factory)
    session = factory()
    yield session
    session.close()
    outer.rollback()
    connection.close()


@pytest.fixture(autouse=True)
def memory_cache():
    cache._redis = None
    cache.mode = "memory"
    cache._memory.clear()
    cache.commands_issued = 0
    yield
    cache._memory.clear()


@pytest.fixture(autouse=True)
def bypass_bucket(monkeypatch):
    monkeypatch.setattr(TokenBucket, "acquire", lambda self, timeout_s=10.0: None)


@pytest.fixture
def universe_bars() -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(11)
    market = rng.normal(0, 0.005, SESSIONS)
    bars = {INDEX_SYMBOL: bars_from_returns(market)}
    for symbol in CORRELATED:
        returns = market + rng.normal(0, 0.002, SESSIONS)
        if symbol == SHOCK_SYMBOL:
            returns[-1] += SHOCK_RETURN
        bars[symbol] = bars_from_returns(returns)
    for symbol in INDEPENDENT:
        bars[symbol] = bars_from_returns(rng.normal(0, 0.01, SESSIONS))
    return bars


def insert_symbols(session, symbols=SYMBOLS) -> None:
    rows = [
        {"symbol": s, "name": s, "industry": "Synthetic", "isin": "", "is_active": True}
        for s in symbols
    ]
    rows.append(
        {
            "symbol": INDEX_SYMBOL,
            "name": "NIFTY 50",
            "industry": "Index",
            "isin": "",
            "is_active": False,
        }
    )
    store.upsert_symbols(session, rows)
    session.commit()


def insert_bars(session, bars: dict[str, pd.DataFrame], upto: int | None = None) -> None:
    for symbol, frame in bars.items():
        store.upsert_bars(session, symbol, bars_of(frame.iloc[:upto]))
    session.commit()


def bars_of(frame: pd.DataFrame) -> list[Bar]:
    return [
        Bar(
            date=stamp.date(),
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
            volume=int(row["volume"]),
        )
        for stamp, row in frame.iterrows()
    ]


def add_watchlist(session, symbols) -> None:
    user = User(id=uuid.uuid4(), display_name="jobs-test")
    session.add(user)
    session.flush()
    session.add_all(WatchlistItem(user_id=user.id, symbol=symbol) for symbol in symbols)
    session.commit()


def chart_history_payload(frame: pd.DataFrame) -> dict:
    timestamps = [
        int(datetime.combine(stamp.date(), clock.OPEN, tzinfo=clock.IST).timestamp())
        for stamp in frame.index
    ]
    quote = {
        column: [float(value) for value in frame[column]]
        for column in ("open", "high", "low", "close")
    }
    quote["volume"] = [int(value) for value in frame["volume"]]
    return {
        "chart": {
            "result": [
                {
                    "meta": {"regularMarketPrice": float(frame["close"].iloc[-1])},
                    "timestamp": timestamps,
                    "indicators": {"quote": [quote]},
                }
            ],
            "error": None,
        }
    }


def chart_quote_payload(
    price: float,
    prev_close: float,
    as_of: datetime,
    day_high: float | None = None,
    day_low: float | None = None,
    volume: int = 1_000_000,
) -> dict:
    meta = {
        "regularMarketPrice": price,
        "chartPreviousClose": prev_close,
        "regularMarketTime": int(as_of.timestamp()),
        "regularMarketDayHigh": day_high if day_high is not None else max(price, prev_close),
        "regularMarketDayLow": day_low if day_low is not None else min(price, prev_close),
        "regularMarketVolume": volume,
    }
    return {
        "chart": {
            "result": [{"meta": meta, "timestamp": [], "indicators": {"quote": [{}]}}],
            "error": None,
        }
    }


def yahoo_route(symbol: str) -> respx.Route:
    return respx.get(host=YAHOO_HOST, path=f"/v8/finance/chart/{symbol}")


def mock_quote(
    symbol: str, price: float, prev_close: float, as_of: datetime, **fields
) -> respx.Route:
    payload = chart_quote_payload(price, prev_close, as_of, **fields)
    return yahoo_route(symbol).mock(return_value=httpx.Response(200, json=payload))


def bse_graph_payload(price: float, prev_close: float) -> dict:
    return {"Data": "[]", "CurrVal": str(price), "PrevClose": str(prev_close)}
