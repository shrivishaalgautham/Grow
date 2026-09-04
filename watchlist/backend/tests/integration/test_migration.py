from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from alembic import command
from app.config import settings

BACKEND = Path(__file__).resolve().parent.parent.parent
EXPECTED_TABLES = {
    "users",
    "sessions",
    "symbols",
    "daily_bars",
    "baselines",
    "peer_clusters",
    "quotes",
    "signal_events",
    "watchlist_items",
    "user_symbol_state",
    "user_rules",
    "briefing_cache",
}

pytestmark = pytest.mark.integration


def alembic_config() -> Config:
    config = Config(str(BACKEND / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND / "alembic"))
    return config


def table_names() -> set[str]:
    engine = create_engine(settings.database_url)
    try:
        return set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def test_upgrade_head_then_downgrade_base_round_trips():
    config = alembic_config()
    command.downgrade(config, "base")
    assert not table_names() & EXPECTED_TABLES

    command.upgrade(config, "head")
    assert EXPECTED_TABLES <= table_names()

    command.downgrade(config, "base")
    assert not table_names() & EXPECTED_TABLES
