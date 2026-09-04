from datetime import datetime

import pytest

from app import clock
from app.cache import cache
from app.clock import IST
from app.config import settings
from app.jobs import scheduler

SATURDAY = datetime(2026, 9, 5, 11, 0, tzinfo=IST)
FRIDAY_OPEN = datetime(2026, 9, 4, 11, 0, tzinfo=IST)


@pytest.fixture
def ticks(monkeypatch):
    calls: list[datetime] = []
    monkeypatch.setattr(scheduler, "refresh_tick", calls.append)
    monkeypatch.setattr(settings, "scheduler_market_hours_only", True)
    return calls


def test_job_returns_when_the_market_is_closed(monkeypatch, ticks):
    monkeypatch.setattr(clock, "now", lambda: SATURDAY)

    scheduler.refresh_job()

    assert ticks == []


def test_job_returns_when_the_lock_is_held(monkeypatch, ticks):
    monkeypatch.setattr(clock, "now", lambda: FRIDAY_OPEN)
    cache.set_nx("refresh:lock", "1", 55)

    scheduler.refresh_job()

    assert ticks == []


def test_job_ticks_and_takes_the_lock_when_open(monkeypatch, ticks):
    monkeypatch.setattr(clock, "now", lambda: FRIDAY_OPEN)

    scheduler.refresh_job()

    assert ticks == [FRIDAY_OPEN]
    assert cache.get("refresh:lock") == "1"
