"""Tests for the model registry: operator-only registration, latest/download."""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user
from app.main import app
from app.models.user import User
from app.security.hashing import hash_password


@pytest.mark.asyncio
async def test_register_model_rejects_non_operator(authed_client: tuple[AsyncClient, User]):
    client, user = authed_client
    assert user.is_operator is False

    files = {"file": ("model.tflite", b"fake-tflite-bytes", "application/octet-stream")}
    response = await client.post(
        "/models/register",
        data={"module_id": "MOD-01", "version": "1.0.0"},
        files=files,
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_register_model_allowed_for_operator(client: AsyncClient, db_session: AsyncSession, tmp_path):
    operator = User(
        email="operator@example.com",
        password_hash=hash_password("StrongPass123"),
        is_operator=True,
    )
    db_session.add(operator)
    await db_session.commit()

    async def _override():
        return operator

    app.dependency_overrides[get_current_user] = _override
    try:
        from app.config import get_settings

        get_settings().MODEL_STORAGE_PATH = str(tmp_path)

        files = {"file": ("model.tflite", b"fake-tflite-bytes", "application/octet-stream")}
        response = await client.post(
            "/models/register",
            data={"module_id": "MOD-01", "version": "1.0.0", "hf_repo_url": "https://huggingface.co/nova/obstacle"},
            files=files,
        )
        assert response.status_code == 201
        body = response.json()
        assert body["module_id"] == "MOD-01"
        assert body["is_active"] is True

        latest = await client.get("/models/latest/MOD-01")
        assert latest.status_code == 200
        assert latest.json()["hf_repo_url"] == "https://huggingface.co/nova/obstacle"

        # Regression check: the file must round-trip from the DB (file_data
        # column), not depend on the ephemeral local disk it used to be
        # written to — that's what silently broke OTA downloads in prod.
        download = await client.get(latest.json()["download_url"])
        assert download.status_code == 200
        assert download.content == b"fake-tflite-bytes"
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_get_latest_model_not_found(authed_client: tuple[AsyncClient, User]):
    client, _ = authed_client
    response = await client.get("/models/latest/MOD-04")
    assert response.status_code == 404
