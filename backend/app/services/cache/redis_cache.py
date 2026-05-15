"""Redis cache abstraction and FastAPI dependency."""

import json
from collections.abc import AsyncGenerator
from typing import Any

from redis.asyncio import Redis

from app.core.config import settings


class RedisCache:
    def __init__(self, client: Redis | None) -> None:
        self._client = client

    async def get_json(self, key: str) -> Any | None:
        if not self._client:
            return None
        raw = await self._client.get(key)
        if raw is None:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode()
        return json.loads(raw)

    async def set_json(self, key: str, value: Any, ttl_seconds: int = 300) -> None:
        if not self._client:
            return
        await self._client.set(key, json.dumps(value, default=str), ex=ttl_seconds)


async def get_redis() -> AsyncGenerator[Redis | None, None]:
    client: Redis | None = None
    try:
        client = Redis.from_url(settings.redis_url, decode_responses=True)
        await client.ping()
        yield client
    except Exception:
        yield None
    finally:
        if client is not None:
            await client.aclose()
