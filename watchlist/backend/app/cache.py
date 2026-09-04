import logging
import time
from collections.abc import Iterable, Mapping

import redis

from app.config import settings

log = logging.getLogger(__name__)


class Cache:
    def __init__(self, redis_url: str) -> None:
        self.commands_issued = 0
        self._memory: dict[str, tuple[str, float | None]] = {}
        self._redis = self._connect(redis_url)
        self.mode = "redis" if self._redis else "memory"

    @staticmethod
    def _connect(redis_url: str) -> redis.Redis | None:
        if not redis_url:
            return None
        try:
            client = redis.Redis.from_url(
                redis_url, socket_connect_timeout=1, socket_timeout=1, decode_responses=True
            )
            client.ping()
            return client
        except (redis.RedisError, OSError) as exc:
            log.warning("cache_fallback mode=memory reason=%s", type(exc).__name__)
            return None

    def get(self, key: str) -> str | None:
        self.commands_issued += 1
        if self._redis:
            return self._redis.get(key)
        return self._memory_get(key)

    def mget(self, keys: Iterable[str]) -> list[str | None]:
        keys = list(keys)
        self.commands_issued += 1
        if self._redis:
            return self._redis.mget(keys) if keys else []
        return [self._memory_get(key) for key in keys]

    def set_many(self, mapping: Mapping[str, str], ttl: int) -> None:
        self.commands_issued += len(mapping)
        if self._redis:
            with self._redis.pipeline(transaction=False) as pipe:
                for key, value in mapping.items():
                    pipe.set(key, value, ex=ttl)
                pipe.execute()
            return
        for key, value in mapping.items():
            self._memory[key] = (value, self._expiry(ttl))

    def set_nx(self, key: str, value: str, ttl: int) -> bool:
        self.commands_issued += 1
        if self._redis:
            return bool(self._redis.set(key, value, nx=True, ex=ttl))
        if self._memory_get(key) is not None:
            return False
        self._memory[key] = (value, self._expiry(ttl))
        return True

    def incr(self, key: str, ttl: int) -> int:
        self.commands_issued += 1
        if self._redis:
            count = self._redis.incr(key)
            if count == 1:
                self.commands_issued += 1
                self._redis.expire(key, ttl)
            return count
        current = self._memory_get(key)
        if current is None:
            self._memory[key] = ("1", self._expiry(ttl))
            return 1
        count = int(current) + 1
        self._memory[key] = (str(count), self._memory[key][1])
        return count

    def delete(self, key: str) -> None:
        self.commands_issued += 1
        if self._redis:
            self._redis.delete(key)
            return
        self._memory.pop(key, None)

    def ping(self) -> bool:
        if not self._redis:
            return True
        try:
            return bool(self._redis.ping())
        except (redis.RedisError, OSError):
            return False

    @staticmethod
    def _expiry(ttl: int) -> float:
        return time.monotonic() + ttl

    def _memory_get(self, key: str) -> str | None:
        entry = self._memory.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if expires_at is not None and expires_at <= time.monotonic():
            del self._memory[key]
            return None
        return value


cache = Cache(settings.redis_url)
