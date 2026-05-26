"""FastAPI application entrypoint."""

from __future__ import annotations

import asyncio
import os
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
from app.db.session import SessionLocal, engine
from app.middleware.exception_handlers import unhandled_exception_handler
from app.middleware.observability import CorrelationIdMiddleware

log = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    log_file = configure_logging(
        json_logs=not settings.debug,
        log_to_file=settings.log_to_file,
        log_dir=settings.log_dir,
    )
    if log_file is not None:
        log.info("logging.file_enabled", path=str(log_file))

    if settings.hf_token and not os.environ.get("HF_TOKEN"):
        os.environ["HF_TOKEN"] = settings.hf_token

    app.state.limiter = limiter
    app.state.db_ok = False
    app.state.redis_ok = False
    app.state.redis_client = None
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        app.state.db_ok = True
    except Exception as e:
        log.warning("db.unavailable", error=str(e))
    try:
        from redis.asyncio import Redis

        _redis = Redis.from_url(settings.redis_url, decode_responses=True)
        await _redis.ping()
        app.state.redis_ok = True
        app.state.redis_client = _redis
        log.info("redis.connected", url=settings.redis_url)
    except Exception as e:
        log.warning("redis.unavailable", error=str(e))

    # QuoteCache — available even without Redis (degrades to in-process dict).
    from app.services.cache.redis_cache import RedisCache
    from app.services.market_data.quote_cache import QuoteCache

    _rc = RedisCache(app.state.redis_client) if app.state.redis_client else None
    app.state.quote_cache = QuoteCache(_rc, ttl_s=settings.quote_cache_ttl_s)

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

    # IBKR Live Market Data — singleton connection + background workers.
    # Started BEFORE the watchlist batch so that opp_service is available on
    # app.state when WatchlistBatchService.from_app_state() is called below.
    # Strictly separate from the analysis batch above; the price worker only
    # writes to ``ticker_market_data`` (via QuoteCache flush) and
    # ``market_candles_1m``; the opportunity worker writes to
    # ``ticker_live_option_opportunities`` and ``ticker_option_opportunity_history``.
    app.state.ibkr = None
    app.state.market_data_service = None
    app.state.market_data_worker = None
    app.state.market_data_pubsub = None
    app.state.opportunity_worker = None
    app.state.opp_service = None  # OptionsOpportunityService — used by WatchlistBatchService
    app.state.redis_pubsub_bridge = None
    if settings.ibkr_enabled:
        try:
            from app.services.dashboard.watchlist import ALL_WATCHLIST_TICKERS
            from app.services.market_data.ibkr_connection import IbkrConnection
            from app.services.market_data.market_data_service import MarketDataService
            from app.services.market_data.opportunity_worker import OpportunityEngineWorker
            from app.services.market_data.options_opportunity_service import (
                OptionsOpportunityService,
            )
            from app.services.market_data.pubsub import MarketDataPubSub
            from app.services.market_data.worker import MarketDataWorker

            ibkr = IbkrConnection(settings)
            app.state.ibkr = ibkr
            connected = await ibkr.connect()
            log.info(
                "ibkr.lifespan.connect",
                connected=connected,
                state=ibkr.state,
                last_error=ibkr.last_error,
            )
            md_service = MarketDataService(settings, ibkr)
            app.state.market_data_service = md_service

            pubsub = MarketDataPubSub(tick_batch_ms=settings.ws_tick_batch_ms)
            app.state.market_data_pubsub = pubsub

            # Optional Redis Pub/Sub bridge for horizontal scaling.
            redis_bridge = None
            if settings.redis_pubsub_enabled and app.state.redis_client is not None:
                from app.services.market_data.redis_pubsub_bridge import RedisPubSubBridge

                redis_bridge = RedisPubSubBridge(
                    redis_client=app.state.redis_client, pubsub=pubsub
                )
                app.state.redis_pubsub_bridge = redis_bridge
                await redis_bridge.start()
                log.info("redis_pubsub_bridge.started")

            worker = MarketDataWorker(
                settings=settings,
                connection=ibkr,
                market_data=md_service,
                watchlist=ALL_WATCHLIST_TICKERS,
                pubsub=pubsub,
                quote_cache=app.state.quote_cache,
                redis_bridge=redis_bridge,
            )
            app.state.market_data_worker = worker
            await worker.start()

            # Opportunity engine — independent worker, reads price from QuoteCache.
            from app.services.market_data.repository import MarketDataRepository

            opp_service = OptionsOpportunityService(
                settings=settings,
                connection=ibkr,
                market_data=md_service,
                repository_factory=lambda: (
                    MarketDataRepository(SessionLocal()),
                    SessionLocal(),
                ),
            )
            # Store on app.state so WatchlistBatchService (created below) picks
            # it up via from_app_state() for IbkrOpportunitySource.
            app.state.opp_service = opp_service

            opp_worker = OpportunityEngineWorker(
                settings=settings,
                opp_service=opp_service,
                pubsub=pubsub,
                quote_cache=app.state.quote_cache,
                watchlist=ALL_WATCHLIST_TICKERS,
                redis_bridge=redis_bridge,
            )
            app.state.opportunity_worker = opp_worker
            await opp_worker.start()

        except Exception as e:  # pragma: no cover - defensive
            log.warning("ibkr.lifespan.startup_failed", error=str(e))
    else:
        log.info("ibkr.lifespan.disabled", note="IBKR_ENABLED=false")

    # Reverse BWB Intelligence Dashboard — sequential watchlist batch.
    # Constructed AFTER IBKR so that from_app_state() picks up opp_service,
    # ibkr connection and quote_cache for live opportunity generation.
    # Route handlers resolve it via ``app.state.watchlist_batch``.
    app.state.watchlist_task = None
    try:
        from app.services.dashboard.watchlist_batch import WatchlistBatchService

        batch = WatchlistBatchService.from_app_state(app, settings)
        if settings.watchlist_auto_run_on_startup and app.state.db_ok:
            log.info(
                "watchlist.startup.scheduling",
                note="WATCHLIST_AUTO_RUN_ON_STARTUP=true — batch will run without UI click",
            )
            app.state.watchlist_task = asyncio.create_task(batch.run_once())
        elif settings.watchlist_auto_run_on_startup and not app.state.db_ok:
            log.warning("watchlist.startup.skipped", reason="db_unavailable")
        else:
            log.info("watchlist.startup.disabled", auto_run=False)
    except Exception as e:  # pragma: no cover - defensive
        log.warning("watchlist.startup.failed", error=str(e))

    yield

    task = getattr(app.state, "watchlist_task", None)
    if task is not None and not task.done():
        task.cancel()
        try:
            await task
        except (asyncio.CancelledError, Exception):  # pragma: no cover
            pass

    # Stop opportunity worker first (it reads from quote cache and pubsub).
    opp_worker = getattr(app.state, "opportunity_worker", None)
    if opp_worker is not None:
        try:
            await opp_worker.stop()
        except Exception as e:  # pragma: no cover - defensive
            log.warning("ibkr.lifespan.stop_opp_worker_failed", error=str(e))

    worker = getattr(app.state, "market_data_worker", None)
    if worker is not None:
        try:
            await worker.stop()
        except Exception as e:  # pragma: no cover - defensive
            log.warning("ibkr.lifespan.stop_worker_failed", error=str(e))

    bridge = getattr(app.state, "redis_pubsub_bridge", None)
    if bridge is not None:
        try:
            await bridge.stop()
        except Exception as e:  # pragma: no cover - defensive
            log.warning("ibkr.lifespan.stop_bridge_failed", error=str(e))

    ibkr = getattr(app.state, "ibkr", None)
    if ibkr is not None:
        try:
            await ibkr.disconnect()
        except Exception as e:  # pragma: no cover - defensive
            log.warning("ibkr.lifespan.disconnect_failed", error=str(e))

    redis_client = getattr(app.state, "redis_client", None)
    if redis_client is not None:
        try:
            await redis_client.aclose()
        except Exception:  # pragma: no cover - defensive
            pass

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
    # CORS must be the OUTERMOST middleware so error responses (429, 500) also
    # carry Access-Control-Allow-Origin. allow_origin_regex is layered on top of
    # the explicit list so any localhost port works during local dev without
    # editing the env file.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
        max_age=600,
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
