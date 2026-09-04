from datetime import UTC, date, datetime

import pytest

from app import clock
from app.clock import IST
from app.config import settings

WEDNESDAY = date(2026, 9, 2)
SATURDAY = date(2026, 9, 5)
SUNDAY = date(2026, 9, 6)


def ist(day: date, hour: int, minute: int) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=IST)


@pytest.mark.parametrize(
    ("at", "expected"),
    [
        (ist(WEDNESDAY, 9, 0), "pre_open"),
        (ist(WEDNESDAY, 9, 15), "open"),
        (ist(WEDNESDAY, 15, 29), "open"),
        (ist(WEDNESDAY, 15, 31), "closed"),
        (ist(WEDNESDAY, 8, 59), "closed"),
        (ist(SATURDAY, 12, 0), "closed"),
    ],
)
def test_market_status(at, expected):
    assert clock.market_status(at) == expected


def test_market_status_converts_from_other_timezones():
    utc_noon = datetime(2026, 9, 2, 4, 0, tzinfo=UTC)
    assert clock.market_status(utc_noon) == "open"


def test_minutes_since_open_clamps_to_session():
    assert clock.minutes_since_open(ist(WEDNESDAY, 8, 0)) == 0
    assert clock.minutes_since_open(ist(WEDNESDAY, 9, 15)) == 0
    assert clock.minutes_since_open(ist(WEDNESDAY, 10, 15)) == 60
    assert clock.minutes_since_open(ist(WEDNESDAY, 15, 30)) == 375
    assert clock.minutes_since_open(ist(WEDNESDAY, 18, 0)) == 375


def test_trading_date_before_open_is_previous_session():
    assert clock.trading_date(ist(WEDNESDAY, 9, 14)) == date(2026, 9, 1)
    assert clock.trading_date(ist(WEDNESDAY, 9, 15)) == WEDNESDAY


def test_trading_date_on_weekend_is_previous_friday():
    assert clock.trading_date(ist(SUNDAY, 12, 0)) == date(2026, 9, 4)
    assert clock.trading_date(ist(SATURDAY, 12, 0)) == date(2026, 9, 4)


def test_trading_date_monday_before_open_is_previous_friday():
    assert clock.trading_date(ist(date(2026, 9, 7), 8, 0)) == date(2026, 9, 4)


def test_replay_date_pins_now(monkeypatch):
    monkeypatch.setattr(settings, "replay_date", date(2026, 9, 1))
    pinned = clock.now()
    assert pinned == datetime(2026, 9, 1, 15, 30, tzinfo=IST)
    assert clock.trading_date(pinned) == date(2026, 9, 1)
    assert clock.minutes_since_open(pinned) == 375


def test_real_clock_is_ist_aware(monkeypatch):
    monkeypatch.setattr(settings, "replay_date", None)
    assert clock.now().utcoffset() == ist(WEDNESDAY, 0, 0).utcoffset()
