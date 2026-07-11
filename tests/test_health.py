"""Tests for the /health readiness probe."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_ok_when_db_reachable(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["checks"]["database"] == "ok"


@pytest.mark.asyncio
async def test_health_degraded_when_db_unreachable(client: AsyncClient, monkeypatch):
    from sqlalchemy.ext.asyncio import AsyncSession

    async def broken_execute(*args, **kwargs):
        raise ConnectionError("simulated DB outage")

    monkeypatch.setattr(AsyncSession, "execute", broken_execute)

    response = await client.get("/health")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["checks"]["database"] == "unreachable"
