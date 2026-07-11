"""Pytest fixtures: an isolated test DB and an async test client.

By default tests run against an in-memory SQLite DB. Setting
``TEST_DATABASE_URL`` (e.g. in CI, pointed at a real Postgres service
container) runs the exact same suite against Postgres, exercising
Postgres-specific behaviour (UUID-as-string columns, server defaults,
cascade deletes) that SQLite can mask.

Scene description and face-matching ML wrappers are monkeypatched so tests
never load PyTorch/InsightFace weights.
"""
import os
from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app import models  # noqa: F401 — registers tables on Base.metadata
from app.database import Base, get_db
from app.dependencies import get_current_user
from app.main import app
from app.models.user import User

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
_IS_SQLITE = TEST_DATABASE_URL.startswith("sqlite")


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    connect_args = {"check_same_thread": False} if _IS_SQLITE else {}
    engine = create_async_engine(TEST_DATABASE_URL, connect_args=connect_args)

    async with engine.begin() as conn:
        # Drop-then-create gives each test a clean schema regardless of
        # backend; SQLite's in-memory DB is already empty per-engine, but
        # a shared Postgres instance retains tables across test runs.
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def authed_client(
    client: AsyncClient, db_session: AsyncSession
) -> AsyncGenerator[tuple[AsyncClient, User], None]:
    """A client pre-authenticated as a freshly created test user."""
    from app.security.hashing import hash_password

    user = User(email="test@example.com", password_hash=hash_password("StrongPass123"))
    db_session.add(user)
    await db_session.commit()

    async def _override_current_user():
        return user

    app.dependency_overrides[get_current_user] = _override_current_user
    yield client, user
    app.dependency_overrides.pop(get_current_user, None)
