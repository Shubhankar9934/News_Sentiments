import pytest


@pytest.mark.asyncio
async def test_health(async_client):
    r = await async_client.get("/api/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "version" in body
