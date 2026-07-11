"""Tests for face enrolment, matching, listing, and deletion.

FaceMatcher.extract_embedding is monkeypatched so tests don't require the
InsightFace model weights to be downloaded.
"""
import base64

import numpy as np
import pytest
from httpx import AsyncClient

from app.ml.face_matcher import FaceMatcher
from app.models.user import User


@pytest.fixture(autouse=True)
def patch_face_extraction(monkeypatch):
    async def fake_extract_embedding(image_bytes: bytes) -> np.ndarray:
        # Deterministic pseudo-embedding derived from the image bytes so
        # repeated enrolments of "the same" image match each other.
        seed = sum(image_bytes) % (2**32)
        rng = np.random.default_rng(seed)
        vec = rng.random(512).astype(np.float32)
        return vec / np.linalg.norm(vec)

    monkeypatch.setattr(FaceMatcher, "extract_embedding", staticmethod(fake_extract_embedding))


@pytest.mark.asyncio
async def test_enrol_and_list_face(authed_client: tuple[AsyncClient, User]):
    client, _ = authed_client
    files = {"face_crop": ("face.jpg", b"fake-image-bytes-aaa", "image/jpeg")}
    response = await client.post("/faces/enrol?contact_name=Mum", files=files)
    assert response.status_code == 201
    body = response.json()
    assert body["contact_name"] == "Mum"

    listing = await client.get("/faces/")
    assert listing.status_code == 200
    assert any(f["contact_name"] == "Mum" for f in listing.json())


@pytest.mark.asyncio
async def test_match_face_against_self(authed_client: tuple[AsyncClient, User]):
    client, _ = authed_client
    image_bytes = b"fake-image-bytes-bbb"
    files = {"face_crop": ("face.jpg", image_bytes, "image/jpeg")}
    await client.post("/faces/enrol?contact_name=Dr+Nkeng", files=files)

    embedding = await FaceMatcher.extract_embedding(image_bytes)
    probe_b64 = base64.b64encode(embedding.tobytes()).decode()

    response = await client.post("/faces/match", json={"embedding_b64": probe_b64})
    assert response.status_code == 200
    body = response.json()
    assert body["match_found"] is True
    assert body["contact_name"] == "Dr Nkeng"


@pytest.mark.asyncio
async def test_delete_enrolled_face(authed_client: tuple[AsyncClient, User]):
    client, _ = authed_client
    files = {"face_crop": ("face.jpg", b"fake-image-bytes-ccc", "image/jpeg")}
    enrol = await client.post("/faces/enrol?contact_name=Friend", files=files)
    face_id = enrol.json()["face_id"]

    response = await client.delete(f"/faces/{face_id}")
    assert response.status_code == 204

    listing = await client.get("/faces/")
    assert all(f["face_id"] != face_id for f in listing.json())


@pytest.mark.asyncio
async def test_delete_nonexistent_face_returns_404(authed_client: tuple[AsyncClient, User]):
    client, _ = authed_client
    response = await client.delete("/faces/does-not-exist")
    assert response.status_code == 404
