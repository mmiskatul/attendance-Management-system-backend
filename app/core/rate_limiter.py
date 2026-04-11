"""Redis-backed or in-memory rate limiter."""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Protocol

from redis.asyncio import Redis

from app.core.exceptions import RateLimitAppError


class RateLimitBackend(Protocol):
    """Backend contract for rate limiting."""

    async def hit(self, key: str, *, limit: int, window_seconds: int) -> tuple[int, int]:
        """Register a hit and return the current count and remaining TTL."""

    async def ping(self) -> bool:
        """Return backend health status."""

    async def close(self) -> None:
        """Close backend resources."""


@dataclass
class InMemoryRateLimitBackend:
    """Process-local fixed-window rate limiter."""

    _events: dict[str, deque[float]]
    _lock: asyncio.Lock

    def __init__(self) -> None:
        self._events = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def hit(self, key: str, *, limit: int, window_seconds: int) -> tuple[int, int]:
        async with self._lock:
            now = time.time()
            cutoff = now - window_seconds
            bucket = self._events[key]
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            bucket.append(now)
            ttl = window_seconds if not bucket else max(1, int(window_seconds - (now - bucket[0])))
            return len(bucket), ttl

    async def ping(self) -> bool:
        return True

    async def close(self) -> None:
        self._events.clear()


class RedisRateLimitBackend:
    """Redis-based fixed-window rate limiter."""

    def __init__(self, redis_url: str) -> None:
        self.redis = Redis.from_url(redis_url, decode_responses=True)

    async def hit(self, key: str, *, limit: int, window_seconds: int) -> tuple[int, int]:
        bucket = int(time.time() // window_seconds)
        redis_key = f"rate_limit:{key}:{bucket}"
        current = await self.redis.incr(redis_key)
        if current == 1:
            await self.redis.expire(redis_key, window_seconds)
        ttl = await self.redis.ttl(redis_key)
        return int(current), max(int(ttl), 1)

    async def ping(self) -> bool:
        return bool(await self.redis.ping())

    async def close(self) -> None:
        await self.redis.close()


class RateLimiter:
    """Service facade for enforcing endpoint limits."""

    def __init__(self, backend: RateLimitBackend) -> None:
        self.backend = backend

    async def enforce(self, key: str, *, limit: int, window_seconds: int) -> None:
        count, ttl = await self.backend.hit(key, limit=limit, window_seconds=window_seconds)
        if count > limit:
            raise RateLimitAppError(f"Rate limit exceeded. Retry in {ttl} seconds.")

    async def health(self) -> bool:
        return await self.backend.ping()

    async def close(self) -> None:
        await self.backend.close()
