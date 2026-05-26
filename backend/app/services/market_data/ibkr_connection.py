"""Singleton IBKR Gateway connection wrapping ``ib_async.IB()``.

One instance per FastAPI process. Production deployments must run uvicorn
with ``--workers 1`` so exactly one process holds the IBKR ``clientId``.

Lifecycle:

    1. ``IbkrConnection.connect()`` from the FastAPI lifespan hook.
    2. ``MarketDataService`` holds a reference and reads ``self.ib`` only
       when ``state == "connected"``.
    3. Reconnect is automatic with exponential backoff (1s, 2s, 5s, 10s,
       30s, 60s capped). The watcher task stays running for the life of
       the process so a brief Gateway restart heals transparently.
    4. ``IbkrConnection.disconnect()`` from lifespan teardown — cancels
       the watcher and disconnects the underlying ``IB()`` cleanly.

Failure mode (per the "hard error" UX choice in the plan):
    - When ``state != "connected"`` every market-data call returns ``None``
      and the worker no-ops. The repository never writes new rows; the
      API returns ``feed_status='disconnected'``.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Literal

import structlog

from app.core.config import Settings

if TYPE_CHECKING:  # pragma: no cover
    from ib_async import IB

log = structlog.get_logger(__name__)

IbkrConnectionState = Literal["disconnected", "connecting", "connected", "failed"]

# Backoff schedule (seconds). Last value is reused for every subsequent
# retry so we don't blow past 1m between attempts during long Gateway
# outages.
_BACKOFF_SCHEDULE_S: tuple[int, ...] = (1, 2, 5, 10, 30, 60)


class IbkrConnection:
    """Owns the single ``ib_async.IB()`` session for the process.

    Construction is cheap (no network IO). Call ``connect()`` exactly once
    from the lifespan to begin the connection lifecycle.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._ib: IB | None = None
        self._state: IbkrConnectionState = "disconnected"
        self._watcher_task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()
        self._connected_event = asyncio.Event()
        self._lock = asyncio.Lock()
        self._last_error: str | None = None
        self._reconnect_attempts = 0

    # ------------------------------------------------------------------ state
    @property
    def state(self) -> IbkrConnectionState:
        return self._state

    @property
    def is_connected(self) -> bool:
        return self._state == "connected" and self._ib is not None and self._ib.isConnected()

    @property
    def last_error(self) -> str | None:
        return self._last_error

    @property
    def ib(self) -> IB | None:
        """Return the underlying client only when fully connected."""
        if self.is_connected:
            return self._ib
        return None

    async def wait_until_connected(self, timeout: float | None = None) -> bool:
        """Block until the next ``connected`` transition (or timeout)."""
        try:
            await asyncio.wait_for(self._connected_event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            return False
        return self.is_connected

    # ------------------------------------------------------------------ lifecycle
    async def connect(self) -> bool:
        """Begin the connection lifecycle. Idempotent.

        Returns True if a fresh connection was established or one was
        already alive, False on initial connect failure (the watcher will
        keep retrying in the background regardless).
        """
        if not self._settings.ibkr_enabled:
            log.info("ibkr.disabled", reason="IBKR_ENABLED=false")
            self._state = "disconnected"
            return False

        async with self._lock:
            if self._watcher_task is None or self._watcher_task.done():
                self._stop_event.clear()
                self._watcher_task = asyncio.create_task(self._watcher_loop())

        ok = await self.wait_until_connected(
            timeout=self._settings.ibkr_connect_timeout_s
        )
        return ok

    async def disconnect(self) -> None:
        """Stop the watcher and disconnect the underlying client."""
        self._stop_event.set()
        task = self._watcher_task
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
        self._watcher_task = None
        await self._teardown_client()
        self._state = "disconnected"
        self._connected_event.clear()

    # ------------------------------------------------------------------ internals
    async def _watcher_loop(self) -> None:
        """Owns the connect/reconnect loop until ``disconnect()`` is called."""
        while not self._stop_event.is_set():
            try:
                await self._attempt_connect()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._last_error = str(exc)
                self._state = "failed"
                self._connected_event.clear()
                log.warning("ibkr.connect_failed", error=str(exc))

            if self._stop_event.is_set():
                break

            if self.is_connected:
                # Wait until either disconnect or external stop.
                await self._wait_until_disconnect_or_stop()
                continue

            self._reconnect_attempts += 1
            backoff = _BACKOFF_SCHEDULE_S[
                min(self._reconnect_attempts - 1, len(_BACKOFF_SCHEDULE_S) - 1)
            ]
            log.info(
                "ibkr.reconnect_scheduled",
                seconds=backoff,
                attempt=self._reconnect_attempts,
            )
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=backoff)
            except asyncio.TimeoutError:
                pass

    async def _attempt_connect(self) -> None:
        try:
            from ib_async import IB
        except ImportError as exc:  # pragma: no cover - dep guard
            self._last_error = (
                "ib_async is not installed. Add `ib-async` to requirements."
            )
            self._state = "failed"
            log.error("ibkr.import_failed", error=str(exc))
            raise

        await self._teardown_client()
        self._state = "connecting"
        self._ib = IB()
        log.info(
            "ibkr.connecting",
            host=self._settings.ibkr_host,
            port=self._settings.ibkr_port,
            client_id=self._settings.ibkr_client_id,
            paper=self._settings.ibkr_paper,
        )
        await self._ib.connectAsync(
            host=self._settings.ibkr_host,
            port=self._settings.ibkr_port,
            clientId=self._settings.ibkr_client_id,
            timeout=self._settings.ibkr_connect_timeout_s,
            readonly=False,
        )
        self._state = "connected"
        self._reconnect_attempts = 0
        self._last_error = None
        self._connected_event.set()
        log.info(
            "ibkr.connected",
            host=self._settings.ibkr_host,
            port=self._settings.ibkr_port,
        )

    async def _wait_until_disconnect_or_stop(self) -> None:
        """Poll ``IB.isConnected()`` until the link drops or stop is set."""
        ib = self._ib
        if ib is None:
            return
        while not self._stop_event.is_set():
            if not ib.isConnected():
                self._state = "disconnected"
                self._connected_event.clear()
                log.warning("ibkr.disconnected_unexpectedly")
                return
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                continue
            else:
                return

    async def _teardown_client(self) -> None:
        ib = self._ib
        self._ib = None
        if ib is None:
            return
        try:
            if ib.isConnected():
                ib.disconnect()
        except Exception as exc:  # pragma: no cover - defensive
            log.warning("ibkr.teardown_failed", error=str(exc))
