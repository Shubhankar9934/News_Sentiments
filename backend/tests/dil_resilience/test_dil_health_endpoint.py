"""Tests for GET /api/v1/dil/health."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from app.services.dil_resilience.registry import reset_resilience_registry


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.asyncio
async def test_dil_health_endpoint() -> None:
    reset_resilience_registry()
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/dil/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "resilience_enabled" in data
    assert "concurrency" in data
    assert "quorum_thresholds" in data
    assert data["concurrency"]["max"] >= 1
