"""WebSocket fanout for the Reverse BWB Trading Workstation.

A single multiplexed socket per client. The client subscribes to one or
more tickers and message types:

    >>> ws.send_json({"action": "subscribe", "tickers": ["SPY", "QQQ"]})
    >>> ws.send_json({"action": "subscribe", "tickers": ["AAPL"], "types": ["tick"]})
    >>> ws.send_json({"action": "ping"})

Server emits two message kinds (see :mod:`app.services.market_data.pubsub`):

    {"type": "tick", ...}                 — every flushed underlying tick
    {"type": "opportunity_version", ...}  — new opportunity cycle landed

Polling REST endpoints remain as a fallback when the socket is closed.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from typing import Any

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.market_data import metrics as md_metrics
from app.services.market_data.pubsub import MarketDataPubSub

log = structlog.get_logger(__name__)
router = APIRouter()


def _get_pubsub(ws: WebSocket) -> MarketDataPubSub | None:
    """Resolve the singleton pubsub from app.state, if the worker is running."""
    app = ws.app
    worker = getattr(app.state, "market_data_worker", None)
    if worker is None:
        return getattr(app.state, "market_data_pubsub", None)
    return worker.pubsub


@router.websocket("/ws/market-data")
async def market_data_socket(ws: WebSocket) -> None:
    """Subscribe to live ticks + opportunity_version push notifications."""
    await ws.accept()
    pubsub = _get_pubsub(ws)
    if pubsub is None:
        await ws.send_json(
            {"type": "error", "detail": "market_data_worker_not_running"}
        )
        await ws.close(code=1011)
        return

    sub = await pubsub.subscribe()
    md_metrics.ws_active_clients.inc()
    forward_task: asyncio.Task[None] | None = None
    try:
        forward_task = asyncio.create_task(_forward_to_socket(ws, sub.queue))
        await _consume_client_messages(ws, pubsub, sub)
    except WebSocketDisconnect:
        log.info("market_data_ws.disconnected")
    except Exception as exc:  # pragma: no cover - defensive
        log.warning("market_data_ws.error", error=str(exc))
    finally:
        if forward_task is not None:
            forward_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await forward_task
        await pubsub.unsubscribe(sub)
        md_metrics.ws_active_clients.dec()
        with contextlib.suppress(Exception):
            await ws.close()


async def _consume_client_messages(
    ws: WebSocket,
    pubsub: MarketDataPubSub,
    sub: Any,
) -> None:
    while True:
        raw = await ws.receive_text()
        try:
            msg: dict[str, Any] = json.loads(raw)
        except json.JSONDecodeError:
            await ws.send_json({"type": "error", "detail": "invalid_json"})
            continue

        action = str(msg.get("action") or "").lower()
        if action == "ping":
            await ws.send_json({"type": "pong"})
            continue
        if action == "subscribe":
            tickers = _str_list(msg.get("tickers"))
            types = _str_list(msg.get("types"))
            await pubsub.update_subscription(
                sub,
                tickers=tickers if tickers is not None else None,
                types=types if types is not None else None,
            )
            await ws.send_json(
                {
                    "type": "subscribed",
                    "tickers": sorted(sub.tickers) if sub.tickers else [],
                    "types": sorted(sub.types),
                }
            )
            continue
        if action == "unsubscribe":
            await pubsub.update_subscription(sub, tickers=[])
            await ws.send_json({"type": "unsubscribed"})
            continue
        await ws.send_json({"type": "error", "detail": "unsupported_action"})


async def _forward_to_socket(ws: WebSocket, queue: asyncio.Queue) -> None:
    """Drain the subscriber queue into the WebSocket."""
    try:
        while True:
            payload = await queue.get()
            await ws.send_json(payload)
    except (WebSocketDisconnect, asyncio.CancelledError):
        return
    except Exception as exc:
        log.warning("market_data_ws.forward_error", error=str(exc))


def _str_list(value: Any) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, list):
        return [str(v) for v in value]
    return [str(value)]
