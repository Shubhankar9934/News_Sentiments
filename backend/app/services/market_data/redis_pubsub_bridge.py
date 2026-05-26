"""Optional Redis Pub/Sub bridge for multi-process WebSocket fanout.

Activated by setting ``REDIS_PUBSUB_ENABLED=true`` (default: false).

When enabled, the IBKR worker process publishes tick/opp_version messages to
two Redis channels instead of the in-process ``MarketDataPubSub``.  Every
API process (including the writer) runs a ``_listen_loop`` task that
subscribes to those channels and re-injects deserialized messages into its
local ``MarketDataPubSub``.  This means each process's WebSocket clients
receive all ticks regardless of which process the IBKR worker is running on.

Architecture (single-process, REDIS_PUBSUB_ENABLED=false — default):

    IBKR Worker ──► MarketDataPubSub ──► WebSocket clients (same process)

Architecture (multi-process, REDIS_PUBSUB_ENABLED=true):

    IBKR Worker ──► Redis channel "market_data:ticks"
                                     │
                    ┌────────────────┘
                    │     (all API processes subscribe)
                    ▼
             MarketDataPubSub ──► WebSocket clients (each process)

The WebSocket route and the worker interface are completely unchanged —
they always talk to the in-process ``MarketDataPubSub``.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from uuid import UUID

from redis.asyncio import Redis

from app.services.market_data.pubsub import (
    MarketDataPubSub,
    OpportunityVersionMessage,
    TickMessage,
)

log = logging.getLogger(__name__)

TICK_CHANNEL = "market_data:ticks"
OPP_CHANNEL = "market_data:opp_versions"


class RedisPubSubBridge:
    """Publishes to and subscribes from Redis Pub/Sub channels.

    A single instance runs in each API process.  The writer calls
    ``publish_tick`` / ``publish_opportunity_version``; the ``_listen_loop``
    deserializes incoming messages and re-injects them into the in-process
    ``MarketDataPubSub``.
    """

    def __init__(self, redis_client: Redis, pubsub: MarketDataPubSub) -> None:
        self._redis = redis_client
        self._pubsub = pubsub
        self._listen_task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()

    # ---------------------------------------------------------------- lifecycle
    async def start(self) -> None:
        """Begin the listener task. Idempotent."""
        if self._listen_task is None or self._listen_task.done():
            self._stop.clear()
            self._listen_task = asyncio.create_task(
                self._listen_loop(), name="redis_pubsub_bridge.listen"
            )

    async def stop(self) -> None:
        """Cancel the listener task."""
        self._stop.set()
        if self._listen_task is not None and not self._listen_task.done():
            self._listen_task.cancel()
            try:
                await self._listen_task
            except (asyncio.CancelledError, Exception):
                pass
        self._listen_task = None

    # --------------------------------------------------------------- publisher
    async def publish_tick(self, msg: TickMessage) -> None:
        """Serialize and publish a tick to the Redis channel."""
        try:
            await self._redis.publish(TICK_CHANNEL, json.dumps(msg.to_payload(), default=str))
        except Exception as exc:
            log.warning("redis_pubsub_bridge.publish_tick.failed err=%s", exc)

    async def publish_opportunity_version(self, msg: OpportunityVersionMessage) -> None:
        """Serialize and publish an opp-version event to the Redis channel."""
        try:
            await self._redis.publish(OPP_CHANNEL, json.dumps(msg.to_payload(), default=str))
        except Exception as exc:
            log.warning("redis_pubsub_bridge.publish_opp.failed err=%s", exc)

    # --------------------------------------------------------------- listener
    async def _listen_loop(self) -> None:
        """Subscribe to both channels and re-inject messages into in-process pubsub."""
        log.info("redis_pubsub_bridge.listen_loop.started channels=%s,%s", TICK_CHANNEL, OPP_CHANNEL)
        while not self._stop.is_set():
            ps = self._redis.pubsub()
            try:
                await ps.subscribe(TICK_CHANNEL, OPP_CHANNEL)
                async for raw in ps.listen():
                    if self._stop.is_set():
                        break
                    if raw.get("type") != "message":
                        continue
                    try:
                        await self._dispatch(raw["channel"], raw["data"])
                    except Exception as exc:
                        log.debug("redis_pubsub_bridge.dispatch_error err=%s", exc)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.warning("redis_pubsub_bridge.listen_loop.error err=%s — reconnecting in 2s", exc)
                await asyncio.sleep(2)
            finally:
                try:
                    await ps.unsubscribe()
                    await ps.aclose()
                except Exception:
                    pass
        log.info("redis_pubsub_bridge.listen_loop.stopped")

    async def _dispatch(self, channel: str, data: str) -> None:
        payload = json.loads(data)
        if channel == TICK_CHANNEL:
            msg = TickMessage(
                ticker=payload["ticker"],
                last_price=payload.get("last"),
                bid=payload.get("bid"),
                ask=payload.get("ask"),
                change_abs=payload.get("change_abs"),
                change_pct=payload.get("change_pct"),
                volume=payload.get("volume"),
                feed_status=payload.get("feed_status", "live"),
                updated_at=(
                    datetime.fromisoformat(payload["ts"])
                    if payload.get("ts")
                    else datetime.now(UTC)
                ),
            )
            await self._pubsub.publish_tick(msg)

        elif channel == OPP_CHANNEL:
            msg_opp = OpportunityVersionMessage(
                ticker=payload["ticker"],
                side=payload["side"],
                opportunity_version=UUID(payload["opportunity_version"]),
                count=int(payload.get("count", 0)),
            )
            await self._pubsub.publish_opportunity_version(msg_opp)


__all__ = ["RedisPubSubBridge"]
