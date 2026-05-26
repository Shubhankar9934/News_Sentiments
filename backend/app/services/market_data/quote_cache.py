"""In-process + Redis cache for the latest live quote per ticker.

The cache sits between the IBKR tick stream and the PostgreSQL persistence
layer.  The worker writes here first (fast, non-blocking), WebSocket
publishing fires immediately, and a separate background loop flushes to
the DB every ``MARKET_DATA_DB_FLUSH_S`` seconds.

REST endpoints that need the latest price read from Redis before touching
the DB, cutting median latency from ~5 ms (Postgres round-trip) to ~0.1 ms
(in-process dict) or ~0.5 ms (Redis round-trip).

Degrades gracefully: if Redis is unavailable, all operations succeed using
the in-process dict only.  The DB flush loop still runs and keeps Postgres
consistent.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from app.services.cache.redis_cache import RedisCache
from app.services.market_data.schemas import LiveQuote

if TYPE_CHECKING:
    pass

log = logging.getLogger(__name__)

_REDIS_KEY_PREFIX = "quote"


class QuoteCache:
    """Two-layer quote cache: in-process dict (authoritative) + Redis sidecar.

    The in-process dict is always up-to-date for the worker process itself.
    Redis makes the latest quote available to other processes (e.g. multiple
    API replicas) without a DB round-trip.
    """

    def __init__(self, redis: RedisCache | None, ttl_s: int = 30) -> None:
        self._redis = redis
        self._ttl_s = max(5, ttl_s)
        self._local: dict[str, LiveQuote] = {}

    # ------------------------------------------------------------------ write

    async def set(self, quote: LiveQuote) -> None:
        """Write to the in-process dict and fire-and-forget to Redis."""
        upper = quote.ticker.upper()
        self._local[upper] = quote
        if self._redis is not None:
            asyncio.ensure_future(self._write_redis(upper, quote))

    def set_local(self, quote: LiveQuote) -> None:
        """Synchronous in-process write only (no Redis, no await)."""
        self._local[quote.ticker.upper()] = quote

    async def _write_redis(self, upper: str, quote: LiveQuote) -> None:
        try:
            await self._redis.set_json(  # type: ignore[union-attr]
                f"{_REDIS_KEY_PREFIX}:{upper}",
                quote.model_dump(mode="json"),
                ttl_seconds=self._ttl_s,
            )
        except Exception as exc:  # pragma: no cover — Redis write failure is non-fatal
            log.debug("quote_cache.redis_write_failed ticker=%s err=%s", upper, exc)

    # ------------------------------------------------------------------ read

    def get_local(self, ticker: str) -> LiveQuote | None:
        """Zero-latency in-process read."""
        return self._local.get(ticker.upper())

    async def get(self, ticker: str) -> LiveQuote | None:
        """In-process dict first; Redis fallback for cross-process reads."""
        upper = ticker.upper()
        local = self._local.get(upper)
        if local is not None:
            return local
        if self._redis is not None:
            try:
                data = await self._redis.get_json(f"{_REDIS_KEY_PREFIX}:{upper}")
                if data is not None:
                    return LiveQuote.model_validate(data)
            except Exception as exc:  # pragma: no cover
                log.debug("quote_cache.redis_read_failed ticker=%s err=%s", upper, exc)
        return None

    def get_all(self) -> dict[str, LiveQuote]:
        """Return a snapshot of all in-process quotes (shallow copy)."""
        return dict(self._local)

    # ----------------------------------------------------------------- misc

    @property
    def size(self) -> int:
        return len(self._local)
