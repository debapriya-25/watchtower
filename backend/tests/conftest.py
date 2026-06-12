"""Pytest fixtures for Phase 2 token-catalogue tests.

Isolation strategy:
  * Each test runs inside a single DB transaction that is **rolled back** at the
    end (via ``join_transaction_mode="create_savepoint"``), so committed seed
    data is never mutated and tests don't leak state.
  * Redis is replaced with an in-memory fake.
  * The CoinGecko HTTP client is monkeypatched per-test (no network calls).
"""

from __future__ import annotations

import asyncio
import sys

# psycopg async requires a SelectorEventLoop on Windows; set before any loop.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import httpx  # noqa: E402
import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.core.security import create_access_token, hash_password  # noqa: E402
from app.db.redis import get_redis  # noqa: E402
from app.db.session import engine, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.enums import UserRole  # noqa: E402
from app.models.user import User  # noqa: E402


class FakeRedis:
    """Minimal in-memory async stand-in for the methods the cache uses."""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> bool:
        self.store[key] = value
        return True

    async def ping(self) -> bool:
        return True

    async def aclose(self) -> None:  # pragma: no cover - parity with real client
        return None


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    """A transactional session bound to one connection, rolled back on teardown."""
    connection = await engine.connect()
    transaction = await connection.begin()
    session = AsyncSession(
        bind=connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    try:
        yield session
    finally:
        await session.close()
        await transaction.rollback()
        await connection.close()


@pytest_asyncio.fixture
async def fake_redis() -> FakeRedis:
    return FakeRedis()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession, fake_redis: FakeRedis):
    """HTTP client with DB + Redis dependencies overridden for isolation."""

    async def _override_get_db():
        # Share the test's transactional session; do not commit/close it here.
        yield db_session

    async def _override_get_redis():
        yield fake_redis

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_redis] = _override_get_redis

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


async def _make_user(
    db: AsyncSession, *, email: str, role: UserRole
) -> tuple[User, dict[str, str]]:
    user = User(
        email=email,
        hashed_password=hash_password("S3curePass!"),
        full_name="Test User",
        role=role,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    access, _, _ = create_access_token(subject=str(user.id))
    return user, {"Authorization": f"Bearer {access}"}


@pytest_asyncio.fixture
async def admin_auth(db_session: AsyncSession) -> dict[str, str]:
    _user, headers = await _make_user(
        db_session, email="admin_test@example.com", role=UserRole.ADMIN
    )
    return headers


@pytest_asyncio.fixture
async def user_auth(db_session: AsyncSession) -> dict[str, str]:
    _user, headers = await _make_user(
        db_session, email="user_test@example.com", role=UserRole.USER
    )
    return headers


@pytest_asyncio.fixture
async def other_user_auth(db_session: AsyncSession) -> dict[str, str]:
    """A second, distinct regular user — used for ownership/403 tests."""
    _user, headers = await _make_user(
        db_session, email="other_user_test@example.com", role=UserRole.USER
    )
    return headers
