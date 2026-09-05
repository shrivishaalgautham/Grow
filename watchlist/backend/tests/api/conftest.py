from pathlib import Path

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from alembic import command
from app.cache import cache
from app.config import settings
from app.db import get_session
from app.main import create_app
from tests.api.support import seed_market

BACKEND = Path(__file__).resolve().parents[2]
MAINTENANCE_URL = "postgresql+psycopg://watchlist:watchlist@localhost:5433/postgres"
TEST_DB = "watchlist_test_api"
TEST_URL = f"{MAINTENANCE_URL.rsplit('/', 1)[0]}/{TEST_DB}"


@pytest.fixture(scope="session")
def test_engine():
    admin = create_engine(MAINTENANCE_URL, isolation_level="AUTOCOMMIT")
    _recreate_database(admin)
    original_url = settings.database_url
    settings.database_url = TEST_URL
    command.upgrade(_alembic_config(), "head")
    engine = create_engine(TEST_URL)
    yield engine
    engine.dispose()
    settings.database_url = original_url
    with admin.connect() as connection:
        connection.execute(text(f"DROP DATABASE IF EXISTS {TEST_DB} WITH (FORCE)"))
    admin.dispose()


@pytest.fixture
def db(test_engine):
    with test_engine.connect() as connection:
        transaction = connection.begin()
        session = Session(
            bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
        )
        yield session
        session.close()
        transaction.rollback()


@pytest.fixture(autouse=True)
def isolated_cache(monkeypatch):
    monkeypatch.setattr(cache, "_redis", None)
    monkeypatch.setattr(cache, "mode", "memory")
    monkeypatch.setattr(settings, "redis_url", "")
    cache._memory.clear()
    if cache._redis:
        cache._redis.flushdb()
    yield
    cache._memory.clear()
    if cache._redis:
        cache._redis.flushdb()


@pytest.fixture
def client(db):
    app = create_app()
    app.dependency_overrides[get_session] = lambda: db
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


@pytest.fixture
def seeded(db):
    return seed_market(db)


def _recreate_database(admin) -> None:
    with admin.connect() as connection:
        connection.execute(text(f"DROP DATABASE IF EXISTS {TEST_DB} WITH (FORCE)"))
        connection.execute(text(f"CREATE DATABASE {TEST_DB}"))


def _alembic_config() -> Config:
    config = Config(str(BACKEND / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND / "alembic"))
    return config
