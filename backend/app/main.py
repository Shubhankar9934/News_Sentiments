"""FastAPI application entrypoint."""

from __future__ import annotations

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text

import app.db  # noqa: F401 — register ORM metadata
from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.constants import API_VERSION
from app.core.logging import configure_logging
from app.core.rate_limit import limiter
from app.db.session import engine
from app.middleware.exception_handlers import unhandled_exception_handler
from app.middleware.observability import CorrelationIdMiddleware

log = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(json_logs=not get_settings().debug)
    settings = get_settings()
    app.state.limiter = limiter
    app.state.db_ok = False
    app.state.redis_ok = False
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        app.state.db_ok = True
    except Exception as e:
        log.warning("db.unavailable", error=str(e))
    try:
        from redis.asyncio import Redis

        r = Redis.from_url(settings.redis_url, decode_responses=True)
        await r.ping()
        app.state.redis_ok = True
        await r.aclose()
    except Exception as e:
        log.warning("redis.unavailable", error=str(e))

    try:
        from app.services.qdrant.store import QdrantStoreService

        app.state.qdrant = QdrantStoreService(settings)
    except Exception as e:
        log.warning("qdrant.unavailable", error=str(e))
        app.state.qdrant = None

    if settings.otel_exporter_otlp_endpoint:
        try:
            from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

            FastAPIInstrumentor.instrument_app(app)
        except Exception as e:
            log.warning("otel.setup_failed", error=str(e))

    yield
    await engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=API_VERSION,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    app.add_middleware(CorrelationIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_exception_handler(RequestValidationError, request_validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    app.include_router(api_router, prefix=settings.api_v1_prefix)

    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> Response:
        data = generate_latest()
        return Response(data, media_type=CONTENT_TYPE_LATEST)

    @app.get("/", include_in_schema=False)
    async def root() -> PlainTextResponse:
        return PlainTextResponse("Financial News Research API")

    return app


app = create_app()
