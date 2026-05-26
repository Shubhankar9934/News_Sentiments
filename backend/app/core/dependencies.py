"""FastAPI dependency providers."""

from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Annotated

from fastapi import Depends, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.session import get_db_session
from app.services.cache.redis_cache import RedisCache, get_redis
from app.services.orchestration.pipeline import ResearchPipelineService
from app.services.qdrant.store import QdrantStoreService

if TYPE_CHECKING:
    from app.services.market_data.quote_cache import QuoteCache


async def get_settings_dep() -> Settings:
    return get_settings()


async def get_redis_dep() -> AsyncGenerator[Redis | None, None]:
    async for r in get_redis():
        yield r


async def get_qdrant(request: Request) -> QdrantStoreService | None:
    return getattr(request.app.state, "qdrant", None)


async def get_quote_cache(request: Request) -> "QuoteCache | None":
    """Return the app-wide QuoteCache populated by the IBKR worker.

    Returns None when IBKR is disabled or the worker hasn't started yet.
    The pipeline degrades gracefully when this is None (falls back to
    Polygon OHLCV for price).
    """
    return getattr(request.app.state, "quote_cache", None)


def get_pipeline_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
    redis: Annotated[Redis | None, Depends(get_redis_dep)],
    qdrant: Annotated[QdrantStoreService | None, Depends(get_qdrant)],
    quote_cache: Annotated["QuoteCache | None", Depends(get_quote_cache)],
) -> ResearchPipelineService:
    cache = RedisCache(redis) if redis else None
    return ResearchPipelineService(
        session=session,
        settings=settings,
        qdrant=qdrant,
        cache=cache,
        quote_cache=quote_cache,
    )


SettingsDep = Annotated[Settings, Depends(get_settings_dep)]
SessionDep = Annotated[AsyncSession, Depends(get_db_session)]
PipelineDep = Annotated[ResearchPipelineService, Depends(get_pipeline_service)]
