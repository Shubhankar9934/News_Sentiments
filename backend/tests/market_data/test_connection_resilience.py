"""Tests for ``IbkrConnection`` lifecycle behavior.

These exercise the connect/disconnect surface without an actual IBKR
Gateway. The ``ib_async`` package may not be installed in the test
environment, so we inject a fake module through ``sys.modules`` before
importing the connection.

The goal is to verify:
    - When IBKR_ENABLED=false, ``connect()`` returns False and never
      starts a watcher.
    - A successful ``connectAsync`` transitions state to ``connected``.
    - A failing ``connectAsync`` leaves state in ``failed`` and the
      watcher schedules a backoff retry.
    - ``disconnect()`` cancels the watcher cleanly.
"""

from __future__ import annotations

import asyncio
import sys
import types
from typing import Any

import pytest

from app.core.config import Settings


class _FakeIB:
    instances: list["_FakeIB"] = []
    _next_succeed: bool = True

    def __init__(self) -> None:
        self.connected_flag = False
        self.succeed = _FakeIB._next_succeed
        self.disconnect_calls = 0
        _FakeIB.instances.append(self)

    async def connectAsync(self, *args: Any, **kwargs: Any) -> None:
        if not self.succeed:
            raise ConnectionError("simulated gateway down")
        self.connected_flag = True

    def isConnected(self) -> bool:
        return self.connected_flag

    def disconnect(self) -> None:
        self.connected_flag = False
        self.disconnect_calls += 1


@pytest.fixture(autouse=True)
def _stub_ib_async(monkeypatch):
    """Inject a fake ``ib_async`` module so the connection import succeeds."""
    fake_module = types.ModuleType("ib_async")
    fake_module.IB = _FakeIB  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "ib_async", fake_module)
    _FakeIB.instances = []
    _FakeIB._next_succeed = True
    yield
    _FakeIB.instances = []


def _settings(enabled: bool = True) -> Settings:
    """Minimal Settings instance for unit tests."""
    return Settings(
        IBKR_ENABLED=enabled,
        IBKR_HOST="127.0.0.1",
        IBKR_PORT=4001,
        IBKR_CLIENT_ID=999,
        IBKR_PAPER=True,
        IBKR_CONNECT_TIMEOUT_S=0.5,
    )


@pytest.mark.asyncio
async def test_disabled_connection_does_not_start_watcher() -> None:
    from app.services.market_data.ibkr_connection import IbkrConnection

    conn = IbkrConnection(_settings(enabled=False))
    ok = await conn.connect()
    assert ok is False
    assert conn.state == "disconnected"


@pytest.mark.asyncio
async def test_successful_connect_transitions_to_connected() -> None:
    from app.services.market_data.ibkr_connection import IbkrConnection

    _FakeIB._next_succeed = True
    conn = IbkrConnection(_settings(enabled=True))
    ok = await conn.connect()
    assert ok is True
    assert conn.state == "connected"
    assert conn.is_connected is True
    await conn.disconnect()
    assert conn.state == "disconnected"


@pytest.mark.asyncio
async def test_failed_connect_leaves_state_in_failed_and_retries() -> None:
    """The watcher should not crash on a bad gateway — it schedules backoff."""
    from app.services.market_data.ibkr_connection import IbkrConnection

    _FakeIB._next_succeed = False
    conn = IbkrConnection(_settings(enabled=True))
    ok = await conn.connect()
    # connect() returns False because the initial attempt didn't reach
    # ``connected`` within the timeout window.
    assert ok is False
    # Watcher is still alive and will keep retrying.
    assert conn._watcher_task is not None  # type: ignore[attr-defined]
    assert not conn._watcher_task.done()  # type: ignore[attr-defined]
    assert conn.state in {"connecting", "failed"}
    await conn.disconnect()


@pytest.mark.asyncio
async def test_disconnect_cancels_watcher() -> None:
    from app.services.market_data.ibkr_connection import IbkrConnection

    _FakeIB._next_succeed = True
    conn = IbkrConnection(_settings(enabled=True))
    await conn.connect()
    await conn.disconnect()
    assert conn._watcher_task is None  # type: ignore[attr-defined]
    assert conn.state == "disconnected"
    assert any(ib.disconnect_calls >= 1 for ib in _FakeIB.instances)


@pytest.mark.asyncio
async def test_ib_property_is_none_when_disconnected() -> None:
    from app.services.market_data.ibkr_connection import IbkrConnection

    conn = IbkrConnection(_settings(enabled=False))
    assert conn.ib is None
    await asyncio.sleep(0)
    assert conn.is_connected is False
