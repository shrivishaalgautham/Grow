from app.cache import cache
from app.jobs import daily
from tests.jobs.conftest import insert_bars, insert_symbols


def test_ensure_seeded_runs_seed_when_no_bars_exist(session, monkeypatch):
    calls = []
    monkeypatch.setattr(daily, "seed", lambda **kwargs: calls.append(kwargs))

    daily.ensure_seeded()

    assert len(calls) == 1


def test_ensure_seeded_skips_when_bars_already_exist(session, universe_bars, monkeypatch):
    insert_symbols(session)
    insert_bars(session, universe_bars)
    calls = []
    monkeypatch.setattr(daily, "seed", lambda **kwargs: calls.append(kwargs))

    daily.ensure_seeded()

    assert calls == []


def test_ensure_seeded_skips_when_the_lock_is_already_held(session, monkeypatch):
    cache.set_nx(daily.BOOTSTRAP_LOCK_KEY, "1", 60)
    calls = []
    monkeypatch.setattr(daily, "seed", lambda **kwargs: calls.append(kwargs))

    daily.ensure_seeded()

    assert calls == []


def test_ensure_seeded_does_not_raise_when_seed_fails(session, monkeypatch):
    def failing(**kwargs):
        raise RuntimeError("yahoo unreachable")

    monkeypatch.setattr(daily, "seed", failing)

    daily.ensure_seeded()
