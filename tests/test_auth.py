"""Tests for registration, login, and token refresh."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_creates_user(client: AsyncClient):
    response = await client.post(
        "/auth/register",
        json={"email": "alice@example.com", "password": "Passw0rd123", "preferred_language": "en-CM"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "alice@example.com"
    assert "id" in body


@pytest.mark.asyncio
async def test_register_duplicate_email_rejected(client: AsyncClient):
    payload = {"email": "bob@example.com", "password": "Passw0rd123"}
    first = await client.post("/auth/register", json=payload)
    assert first.status_code == 201

    second = await client.post("/auth/register", json=payload)
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_register_rejects_weak_password(client: AsyncClient):
    response = await client.post(
        "/auth/register", json={"email": "weak@example.com", "password": "onlyletters"}
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_login_success_returns_tokens(client: AsyncClient):
    await client.post(
        "/auth/register", json={"email": "carol@example.com", "password": "Passw0rd123"}
    )
    response = await client.post(
        "/auth/login", data={"username": "carol@example.com", "password": "Passw0rd123"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["refresh_token"]


@pytest.mark.asyncio
async def test_login_wrong_password_rejected(client: AsyncClient):
    await client.post(
        "/auth/register", json={"email": "dave@example.com", "password": "Passw0rd123"}
    )
    response = await client.post(
        "/auth/login", data={"username": "dave@example.com", "password": "WrongPass1"}
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token_issues_new_pair(client: AsyncClient):
    await client.post(
        "/auth/register", json={"email": "erin@example.com", "password": "Passw0rd123"}
    )
    login = await client.post(
        "/auth/login", data={"username": "erin@example.com", "password": "Passw0rd123"}
    )
    refresh_token = login.json()["refresh_token"]

    response = await client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert response.status_code == 200
    assert response.json()["access_token"]


@pytest.mark.asyncio
async def test_refresh_rejects_access_token(client: AsyncClient):
    await client.post(
        "/auth/register", json={"email": "frank@example.com", "password": "Passw0rd123"}
    )
    login = await client.post(
        "/auth/login", data={"username": "frank@example.com", "password": "Passw0rd123"}
    )
    access_token = login.json()["access_token"]

    response = await client.post("/auth/refresh", json={"refresh_token": access_token})
    assert response.status_code == 401
