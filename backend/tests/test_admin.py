"""Admin user-management endpoint tests.

Covered: list users, pagination, deactivate, reactivate, non-admin 403, and
unknown-user 404.

Each test resets the ``users`` table inside its rolled-back transaction and
seeds a known set, so list/pagination assertions are deterministic regardless of
any committed data in the dev database.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password
from app.models.enums import UserRole
from app.models.user import User

pytestmark = pytest.mark.asyncio

BASE = "/api/v1/admin"


async def _reset_users(db: AsyncSession) -> None:
    await db.execute(delete(User))
    await db.flush()


async def _make_user(
    db: AsyncSession,
    email: str,
    *,
    role: UserRole = UserRole.USER,
    is_active: bool = True,
) -> User:
    user = User(
        email=email,
        hashed_password=hash_password("S3curePass!"),
        full_name="Test User",
        role=role,
        is_active=is_active,
    )
    db.add(user)
    await db.flush()
    return user


def _auth(user: User) -> dict[str, str]:
    access, _, _ = create_access_token(subject=str(user.id))
    return {"Authorization": f"Bearer {access}"}


# --------------------------------------------------------------------------- #
# List + pagination
# --------------------------------------------------------------------------- #
async def test_admin_list_users(client, db_session):
    await _reset_users(db_session)
    admin = await _make_user(db_session, "admin@t.io", role=UserRole.ADMIN)
    await _make_user(db_session, "u1@t.io")
    await _make_user(db_session, "u2@t.io")

    resp = await client.get(f"{BASE}/users", headers=_auth(admin))
    assert resp.status_code == 200

    body = resp.json()
    assert body["success"] is True and body["error"] is None
    data = body["data"]
    assert data["pagination"]["total"] == 3
    # Required fields are present; the password hash is never exposed.
    sample = data["items"][0]
    assert set(sample) >= {
        "id", "email", "role", "is_active", "created_at", "updated_at"
    }
    assert "hashed_password" not in sample and "password" not in sample


async def test_admin_list_pagination(client, db_session):
    await _reset_users(db_session)
    admin = await _make_user(db_session, "admin@t.io", role=UserRole.ADMIN)
    for i in range(4):
        await _make_user(db_session, f"user{i}@t.io")
    # 5 users total (1 admin + 4).

    page1 = await client.get(
        f"{BASE}/users", params={"page": 1, "size": 2}, headers=_auth(admin)
    )
    assert page1.status_code == 200
    p1 = page1.json()["data"]
    assert len(p1["items"]) == 2
    assert p1["pagination"] == {"page": 1, "size": 2, "total": 5, "pages": 3}

    page3 = await client.get(
        f"{BASE}/users", params={"page": 3, "size": 2}, headers=_auth(admin)
    )
    assert len(page3.json()["data"]["items"]) == 1  # remainder on last page


# --------------------------------------------------------------------------- #
# Activate / deactivate
# --------------------------------------------------------------------------- #
async def test_admin_deactivate_user(client, db_session):
    await _reset_users(db_session)
    admin = await _make_user(db_session, "admin@t.io", role=UserRole.ADMIN)
    target = await _make_user(db_session, "victim@t.io", is_active=True)

    resp = await client.patch(
        f"{BASE}/users/{target.id}",
        json={"is_active": False},
        headers=_auth(admin),
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["id"] == str(target.id)
    assert data["is_active"] is False


async def test_admin_reactivate_user(client, db_session):
    await _reset_users(db_session)
    admin = await _make_user(db_session, "admin@t.io", role=UserRole.ADMIN)
    target = await _make_user(db_session, "dormant@t.io", is_active=False)

    resp = await client.patch(
        f"{BASE}/users/{target.id}",
        json={"is_active": True},
        headers=_auth(admin),
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["is_active"] is True


# --------------------------------------------------------------------------- #
# RBAC + not-found
# --------------------------------------------------------------------------- #
async def test_non_admin_forbidden(client, db_session):
    await _reset_users(db_session)
    admin = await _make_user(db_session, "admin@t.io", role=UserRole.ADMIN)
    regular = await _make_user(db_session, "regular@t.io", role=UserRole.USER)

    list_resp = await client.get(f"{BASE}/users", headers=_auth(regular))
    patch_resp = await client.patch(
        f"{BASE}/users/{admin.id}",
        json={"is_active": False},
        headers=_auth(regular),
    )
    for resp in (list_resp, patch_resp):
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "permission_denied"


async def test_list_requires_authentication(client, db_session):
    await _reset_users(db_session)
    resp = await client.get(f"{BASE}/users")
    assert resp.status_code == 401


async def test_unknown_user_returns_404(client, db_session):
    await _reset_users(db_session)
    admin = await _make_user(db_session, "admin@t.io", role=UserRole.ADMIN)

    resp = await client.patch(
        f"{BASE}/users/{uuid.uuid4()}",
        json={"is_active": False},
        headers=_auth(admin),
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"
