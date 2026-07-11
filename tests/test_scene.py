"""Tests for the scene description endpoint, with SceneDescriber mocked."""
import io

import pytest
from httpx import AsyncClient
from PIL import Image

from app.ml.scene_describer import SceneDescriber
from app.models.user import User


def _make_jpeg_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (32, 32), color="red").save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture(autouse=True)
def patch_scene_describer(monkeypatch):
    async def fake_describe(image_bytes: bytes) -> str:
        return "A red square is visible in front of you."

    monkeypatch.setattr(SceneDescriber, "describe", staticmethod(fake_describe))


@pytest.mark.asyncio
async def test_describe_scene_requires_auth(client: AsyncClient):
    files = {"image": ("scene.jpg", _make_jpeg_bytes(), "image/jpeg")}
    response = await client.post("/scene/describe", files=files)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_describe_scene_returns_description(authed_client: tuple[AsyncClient, User]):
    client, _ = authed_client
    files = {"image": ("scene.jpg", _make_jpeg_bytes(), "image/jpeg")}
    response = await client.post("/scene/describe", files=files)
    assert response.status_code == 200
    assert "red square" in response.json()["description"]


@pytest.mark.asyncio
async def test_describe_scene_rejects_oversized_image(authed_client: tuple[AsyncClient, User]):
    client, _ = authed_client
    oversized = b"\xff\xd8" + b"0" * (513 * 1024)  # fake JPEG header + filler
    files = {"image": ("scene.jpg", oversized, "image/jpeg")}
    response = await client.post("/scene/describe", files=files)
    assert response.status_code == 413


@pytest.mark.asyncio
async def test_describe_scene_rejects_invalid_content_type(authed_client: tuple[AsyncClient, User]):
    client, _ = authed_client
    files = {"image": ("scene.txt", b"not an image", "text/plain")}
    response = await client.post("/scene/describe", files=files)
    assert response.status_code == 400
