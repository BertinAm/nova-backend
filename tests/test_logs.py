"""Tests for usage event and feedback sync (idempotency, auth requirement)."""
import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient

from app.models.user import User


@pytest.mark.asyncio
async def test_sync_logs_requires_auth(client: AsyncClient):
    response = await client.post("/logs/sync", json={"events": []})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_sync_logs_inserts_events_idempotently(authed_client: tuple[AsyncClient, User]):
    client, _ = authed_client
    event_id = str(uuid.uuid4())
    payload = {
        "events": [
            {
                "id": event_id,
                "module_id": "MOD-01",
                "timestamp": datetime.now(UTC).isoformat(),
                "outcome": "success",
                "confidence_score": 0.92,
            }
        ]
    }

    first = await client.post("/logs/sync", json=payload)
    assert first.status_code == 200
    assert first.json() == {"inserted": 1, "total": 1}

    # Re-sending the same event ID must not create a duplicate row.
    second = await client.post("/logs/sync", json=payload)
    assert second.status_code == 200
    assert second.json() == {"inserted": 0, "total": 1}


@pytest.mark.asyncio
async def test_sync_logs_rejects_invalid_module_id(authed_client: tuple[AsyncClient, User]):
    client, _ = authed_client
    payload = {
        "events": [
            {
                "id": str(uuid.uuid4()),
                "module_id": "NOT-A-MODULE",
                "timestamp": datetime.now(UTC).isoformat(),
                "outcome": "success",
            }
        ]
    }
    response = await client.post("/logs/sync", json=payload)
    assert response.status_code == 422
