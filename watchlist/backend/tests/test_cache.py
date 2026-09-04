import time

from app.cache import Cache


def memory_cache() -> Cache:
    cache = Cache("")
    assert cache.mode == "memory"
    return cache


def test_set_many_then_mget_round_trips():
    cache = memory_cache()
    cache.set_many({"a": "1", "b": "2"}, ttl=60)
    assert cache.mget(["a", "b", "missing"]) == ["1", "2", None]
    assert cache.get("a") == "1"


def test_set_many_counts_one_command_per_key():
    cache = memory_cache()
    before = cache.commands_issued
    cache.set_many({"a": "1", "b": "2", "c": "3"}, ttl=60)
    assert cache.commands_issued - before == 3


def test_entries_expire(monkeypatch):
    cache = memory_cache()
    cache.set_many({"a": "1"}, ttl=10)
    start = time.monotonic()
    monkeypatch.setattr(time, "monotonic", lambda: start + 11)
    assert cache.get("a") is None


def test_set_nx_only_first_writer_wins():
    cache = memory_cache()
    assert cache.set_nx("lock", "x", ttl=60) is True
    assert cache.set_nx("lock", "y", ttl=60) is False
    assert cache.get("lock") == "x"


def test_set_nx_succeeds_after_expiry(monkeypatch):
    cache = memory_cache()
    cache.set_nx("lock", "x", ttl=5)
    start = time.monotonic()
    monkeypatch.setattr(time, "monotonic", lambda: start + 6)
    assert cache.set_nx("lock", "y", ttl=5) is True


def test_incr_counts_and_keeps_original_expiry(monkeypatch):
    cache = memory_cache()
    start = time.monotonic()
    monkeypatch.setattr(time, "monotonic", lambda: start)
    assert cache.incr("rl", ttl=10) == 1
    monkeypatch.setattr(time, "monotonic", lambda: start + 8)
    assert cache.incr("rl", ttl=10) == 2
    monkeypatch.setattr(time, "monotonic", lambda: start + 11)
    assert cache.incr("rl", ttl=10) == 1


def test_delete_removes_key():
    cache = memory_cache()
    cache.set_many({"a": "1"}, ttl=60)
    cache.delete("a")
    assert cache.get("a") is None


def test_ping_in_memory_mode():
    assert memory_cache().ping() is True


def test_unreachable_redis_falls_back_to_memory():
    cache = Cache("redis://127.0.0.1:1/0")
    assert cache.mode == "memory"
    cache.set_many({"a": "1"}, ttl=60)
    assert cache.get("a") == "1"
