"""Tests for emergency contact CRUD (FR-06-04)."""
import pytest
from httpx import AsyncClient

from app.models.user import User


@pytest.mark.asyncio
async def test_get_emergency_contact_requires_auth(client: AsyncClient):
    response = await client.get("/emergency-contact/")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_emergency_contact_not_set_returns_404(authed_client: tuple[AsyncClient, User]):
    client, _ = authed_client
    response = await client.get("/emergency-contact/")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_set_and_get_emergency_contact(authed_client: tuple[AsyncClient, User]):
    client, _ = authed_client
    response = await client.put(
        "/emergency-contact/", json={"contact_name": "Mum", "phone_number": "+237670000000"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["contact_name"] == "Mum"
    assert body["phone_number"] == "+237670000000"

    fetched = await client.get("/emergency-contact/")
    assert fetched.status_code == 200
    assert fetched.json()["phone_number"] == "+237670000000"


@pytest.mark.asyncio
async def test_set_emergency_contact_overwrites_existing(authed_client: tuple[AsyncClient, User]):
    client, _ = authed_client
    await client.put(
        "/emergency-contact/", json={"contact_name": "Mum", "phone_number": "+237670000000"}
    )
    response = await client.put(
        "/emergency-contact/", json={"contact_name": "Dad", "phone_number": "+237680000000"}
    )
    assert response.status_code == 200
    assert response.json()["contact_name"] == "Dad"

    fetched = await client.get("/emergency-contact/")
    assert fetched.json()["contact_name"] == "Dad"


@pytest.mark.asyncio
async def test_set_emergency_contact_rejects_invalid_phone(authed_client: tuple[AsyncClient, User]):
    client, _ = authed_client
    response = await client.put(
        "/emergency-contact/", json={"contact_name": "Mum", "phone_number": "not-a-phone"}
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_delete_emergency_contact(authed_client: tuple[AsyncClient, User]):
    client, _ = authed_client
    await client.put(
        "/emergency-contact/", json={"contact_name": "Mum", "phone_number": "+237670000000"}
    )
    response = await client.delete("/emergency-contact/")
    assert response.status_code == 204

    fetched = await client.get("/emergency-contact/")
    assert fetched.status_code == 404


@pytest.mark.asyncio
async def test_delete_emergency_contact_not_set_returns_404(authed_client: tuple[AsyncClient, User]):
    client, _ = authed_client
    response = await client.delete("/emergency-contact/")
    assert response.status_code == 404
