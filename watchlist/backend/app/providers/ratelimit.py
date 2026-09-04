import math
import time
from datetime import UTC, datetime
from typing import Literal

from app.cache import cache
from app.providers.base import ProviderError

WINDOW_EDGE_SLACK_S = 0.01
STATE_TTL_SECONDS = 86400

CircuitState = Literal["closed", "open", "half_open"]


class TokenBucket:
    def __init__(self, name: str, rate_per_sec: float) -> None:
        if rate_per_sec <= 0:
            raise ValueError("rate_per_sec must be positive")
        self.name = name
        self.window_s = 1 if rate_per_sec >= 1 else math.ceil(1 / rate_per_sec)
        self.capacity = max(1, int(rate_per_sec * self.window_s))

    def acquire(self, timeout_s: float = 10.0) -> None:
        deadline = time.monotonic() + timeout_s
        while not self._try_take():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ProviderError(self.name, "rate limit wait timed out", retryable=True)
            time.sleep(min(self._seconds_until_next_window(), remaining))

    def _try_take(self) -> bool:
        window = int(time.time()) // self.window_s
        count = cache.incr(f"tb:{self.name}:{window}", ttl=self.window_s + 1)
        return count <= self.capacity

    def _seconds_until_next_window(self) -> float:
        return self.window_s - (time.time() % self.window_s) + WINDOW_EDGE_SLACK_S


class CircuitBreaker:
    def __init__(self, name: str, failure_threshold: int = 3, open_seconds: int = 60) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.open_seconds = open_seconds
        self._failures_key = f"cb:{name}:failures"
        self._opened_at_key = f"cb:{name}:opened_at"
        self._last_success_key = f"cb:{name}:last_success"

    def allow(self) -> bool:
        return self.state() != "open"

    def record_success(self) -> None:
        failures, opened_at = cache.mget([self._failures_key, self._opened_at_key])
        if failures is not None:
            cache.delete(self._failures_key)
        if opened_at is not None:
            cache.delete(self._opened_at_key)
        cache.set_many({self._last_success_key: str(time.time())}, ttl=STATE_TTL_SECONDS)

    def record_failure(self) -> None:
        failures = cache.incr(self._failures_key, ttl=STATE_TTL_SECONDS)
        if failures >= self.failure_threshold:
            cache.set_many({self._opened_at_key: str(time.time())}, ttl=STATE_TTL_SECONDS)

    def state(self) -> CircuitState:
        return self._state_from(cache.get(self._opened_at_key))

    def snapshot(self) -> dict:
        failures, opened_at, last_success = cache.mget(
            [self._failures_key, self._opened_at_key, self._last_success_key]
        )
        return {
            "provider": self.name,
            "circuit_state": self._state_from(opened_at),
            "last_success_at": _iso_or_none(last_success),
            "consecutive_failures": int(failures or 0),
        }

    def _state_from(self, opened_at: str | None) -> CircuitState:
        if opened_at is None:
            return "closed"
        if time.time() - float(opened_at) >= self.open_seconds:
            return "half_open"
        return "open"


def _iso_or_none(epoch: str | None) -> str | None:
    if epoch is None:
        return None
    return datetime.fromtimestamp(float(epoch), UTC).isoformat()
