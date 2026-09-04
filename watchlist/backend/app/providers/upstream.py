import logging
import time

import httpx

from app.providers.base import ProviderError
from app.providers.ratelimit import CircuitBreaker, TokenBucket

log = logging.getLogger(__name__)

MAX_RETRIES = 3


class Upstream:
    def __init__(self, provider: str, client: httpx.Client, rate_per_sec: float) -> None:
        self.provider = provider
        self.client = client
        self.bucket = TokenBucket(provider, rate_per_sec)
        # one request exhausting its retry budget must not open the circuit on its own
        self.breaker = CircuitBreaker(provider, failure_threshold=MAX_RETRIES + 1)

    def get(self, op: str, symbol: str, url: str, params: dict[str, str]) -> httpx.Response:
        if not self.breaker.allow():
            raise ProviderError(self.provider, "circuit open", retryable=True)
        self.bucket.acquire()
        started = time.monotonic()
        try:
            response = self.client.get(url, params=params)
        except httpx.HTTPError as exc:
            self.breaker.record_failure()
            self._log(op, symbol, f"error error={type(exc).__name__}", started)
            raise ProviderError(
                self.provider, f"{op} {symbol}: {type(exc).__name__}", retryable=True
            ) from exc
        self._log(op, symbol, str(response.status_code), started)
        self._record(response.status_code)
        return response

    def status_error(self, op: str, symbol: str, response: httpx.Response) -> ProviderError:
        status = response.status_code
        return ProviderError(
            self.provider,
            f"{op} {symbol}: HTTP {status}",
            status=status,
            retryable=status == 429 or status >= 500,
        )

    def _record(self, status: int) -> None:
        if status == 200:
            self.breaker.record_success()
        elif status != 404:
            self.breaker.record_failure()

    def _log(self, op: str, symbol: str, status: str, started: float) -> None:
        elapsed_ms = int((time.monotonic() - started) * 1000)
        log.info(
            "provider=%s op=%s symbol=%s status=%s ms=%d",
            self.provider,
            op,
            symbol,
            status,
            elapsed_ms,
        )
