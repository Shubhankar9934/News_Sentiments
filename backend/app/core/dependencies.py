"""FastAPI dependency providers."""

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.session import get_db_session
from app.services.cache.redis_cache import RedisCache, get_redis
from app.services.orchestration.pipeline import ResearchPipelineService
from app.services.qdrant.store import QdrantStoreService


async def get_settings_dep() -> Settings:
    return get_settings()


async def get_redis_dep() -> AsyncGenerator[Redis | None, None]:
    async for r in get_redis():
        yield r


async def get_qdrant(request: Request) -> QdrantStoreService | None:
    return getattr(request.app.state, "qdrant", None)


def get_pipeline_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings_dep)],
    redis: Annotated[Redis | None, Depends(get_redis_dep)],
    qdrant: Annotated[QdrantStoreService | None, Depends(get_qdrant)],
) -> ResearchPipelineService:
    cache = RedisCache(redis) if redis else None
    return ResearchPipelineService(
        session=session,
        settings=settings,
        qdrant=qdrant,
        cache=cache,
    )


SettingsDep = Annotated[Settings, Depends(get_settings_dep)]
SessionDep = Annotated[AsyncSession, Depends(get_db_session)]
PipelineDep = Annotated[ResearchPipelineService, Depends(get_pipeline_service)]
