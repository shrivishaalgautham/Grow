import time
import uuid

import pytest

from app.cache import cache
from app.providers.base import ProviderError
from app.providers.ratelimit import CircuitBreaker, TokenBucket


def unique_name() -> str:
    return f"test-{uuid.uuid4().hex[:8]}"


def freeze_clock(monkeypatch, at: float) -> None:
    monkeypatch.setattr(time, "time", lambda: at)


def test_bucket_allows_rate_calls_per_second_then_raises_on_timeout(monkeypatch):
    freeze_clock(monkeypatch, 1_000_000.0)
    bucket = TokenBucket(unique_name(), rate_per_sec=2)
    bucket.acquire(timeout_s=0)
    bucket.acquire(timeout_s=0)
    with pytest.raises(ProviderError) as excinfo:
        bucket.acquire(timeout_s=0)
    assert excinfo.value.retryable is True


def test_bucket_refills_in_the_next_second(monkeypatch):
    freeze_clock(monkeypatch, 1_000_000.0)
    bucket = TokenBucket(unique_name(), rate_per_sec=1)
    bucket.acquire(timeout_s=0)
    freeze_clock(monkeypatch, 1_000_001.0)
    bucket.acquire(timeout_s=0)


def test_bucket_waits_for_a_slot_before_the_deadline(monkeypatch):
    now = [1_000_000.0]
    monkeypatch.setattr(time, "time", lambda: now[0])
    monkeypatch.setattr(time, "sleep", lambda seconds: now.__setitem__(0, now[0] + 1))
    bucket = TokenBucket(unique_name(), rate_per_sec=1)
    bucket.acquire(timeout_s=5)
    before = cache.commands_issued
    bucket.acquire(timeout_s=5)
    assert cache.commands_issued - before == 2


def test_sub_one_rps_allows_one_call_per_window(monkeypatch):
    freeze_clock(monkeypatch, 1_000_000.0)
    bucket = TokenBucket(unique_name(), rate_per_sec=0.5)
    bucket.acquire(timeout_s=0)
    with pytest.raises(ProviderError):
        bucket.acquire(timeout_s=0)


def test_breaker_opens_after_three_failures_and_recovers(monkeypatch):
    freeze_clock(monkeypatch, 1_000_000.0)
    breaker = CircuitBreaker(unique_name(), failure_threshold=3, open_seconds=60)
    breaker.record_failure()
    breaker.record_failure()
    assert breaker.state() == "closed"
    assert breaker.allow() is True
    breaker.record_failure()
    assert breaker.state() == "open"
    assert breaker.allow() is False

    freeze_clock(monkeypatch, 1_000_060.0)
    assert breaker.state() == "half_open"
    assert breaker.allow() is True

    breaker.record_success()
    assert breaker.state() == "closed"
    assert breaker.snapshot()["consecutive_failures"] == 0


def test_half_open_failure_reopens(monkeypatch):
    freeze_clock(monkeypatch, 1_000_000.0)
    breaker = CircuitBreaker(unique_name(), failure_threshold=3, open_seconds=60)
    for _ in range(3):
        breaker.record_failure()
    freeze_clock(monkeypatch, 1_000_061.0)
    assert breaker.state() == "half_open"
    breaker.record_failure()
    assert breaker.state() == "open"
    assert breaker.allow() is False


def test_success_resets_consecutive_failures():
    breaker = CircuitBreaker(unique_name())
    breaker.record_failure()
    breaker.record_failure()
    breaker.record_success()
    breaker.record_failure()
    assert breaker.state() == "closed"
    assert breaker.snapshot()["consecutive_failures"] == 1


def test_snapshot_exposes_exactly_the_health_fields(monkeypatch):
    freeze_clock(monkeypatch, 1_000_000.0)
    name = unique_name()
    breaker = CircuitBreaker(name)
    assert breaker.snapshot() == {
        "provider": name,
        "circuit_state": "closed",
        "last_success_at": None,
        "consecutive_failures": 0,
    }
    breaker.record_success()
    snapshot = breaker.snapshot()
    assert set(snapshot) == {"provider", "circuit_state", "last_success_at", "consecutive_failures"}
    assert snapshot["last_success_at"] == "1970-01-12T13:46:40+00:00"


def test_breaker_state_is_shared_across_instances_with_the_same_name():
    name = unique_name()
    for _ in range(3):
        CircuitBreaker(name).record_failure()
    assert CircuitBreaker(name).allow() is False
