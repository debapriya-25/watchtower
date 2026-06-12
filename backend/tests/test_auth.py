"""Authentication endpoint tests (happy paths + 401/409).

Exercises the real ``/auth`` endpoints end-to-end (register -> login -> /me ->
refresh) plus the key failure modes, satisfying the PRD acceptance criterion of
tests covering auth happy + 401/403 paths. RBAC 403 is covered in the token /
admin / ownership test modules.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio

EMAIL = "auth_flow@example.com"
PASSWORD = "S3curePass!"


async def _register(client, email=EMAIL, password=PASSWORD, full_name="Auth Flow"):
    return await client.post(
        "/auth/register",
        json={"email": email, "password": password, "full_name": full_name},
    )


# --------------------------------------------------------------------------- #
# Register
# --------------------------------------------------------------------------- #
async def test_register_happy_path(client, db_session):
    resp = await _register(client)
    assert resp.status_code == 201

    body = resp.json()
    assert body["success"] is True and body["error"] is None
    data = body["data"]
    assert data["user"]["email"] == EMAIL
    assert data["user"]["role"] == "user"
    assert data["user"]["is_active"] is True
    assert "hashed_password" not in data["user"]
    tokens = data["tokens"]
    assert tokens["access_token"] and tokens["refresh_token"]
    assert tokens["token_type"] == "bearer"
    assert tokens["expires_in"] == 15 * 60


async def test_register_duplicate_email_conflict(client, db_session):
    await _register(client)
    resp = await _register(client)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "conflict"


async def test_register_invalid_payload_422(client, db_session):
    resp = await client.post(
        "/auth/register", json={"email": "not-an-email", "password": "short"}
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"


# --------------------------------------------------------------------------- #
# Login
# --------------------------------------------------------------------------- #
async def test_login_happy_path(client, db_session):
    await _register(client)
    resp = await client.post(
        "/auth/login", json={"email": EMAIL, "password": PASSWORD}
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["user"]["email"] == EMAIL
    assert data["tokens"]["access_token"]


async def test_login_wrong_password_401(client, db_session):
    await _register(client)
    resp = await client.post(
        "/auth/login", json={"email": EMAIL, "password": "WrongPass1!"}
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "authentication_failed"


async def test_login_unknown_user_401(client, db_session):
    resp = await client.post(
        "/auth/login", json={"email": "nobody@example.com", "password": PASSWORD}
    )
    assert resp.status_code == 401


# --------------------------------------------------------------------------- #
# /me
# --------------------------------------------------------------------------- #
async def test_me_happy_path(client, db_session):
    access = (await _register(client)).json()["data"]["tokens"]["access_token"]
    resp = await client.get(
        "/auth/me", headers={"Authorization": f"Bearer {access}"}
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["email"] == EMAIL


async def test_me_requires_auth_401(client, db_session):
    resp = await client.get("/auth/me")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "authentication_failed"


async def test_me_rejects_invalid_token_401(client, db_session):
    resp = await client.get(
        "/auth/me", headers={"Authorization": "Bearer not.a.real.jwt"}
    )
    assert resp.status_code == 401


# --------------------------------------------------------------------------- #
# Refresh (rotation)
# --------------------------------------------------------------------------- #
async def test_refresh_rotates_tokens(client, db_session):
    refresh = (await _register(client)).json()["data"]["tokens"]["refresh_token"]

    resp = await client.post("/auth/refresh", json={"refresh_token": refresh})
    assert resp.status_code == 200
    new_tokens = resp.json()["data"]
    assert new_tokens["access_token"] and new_tokens["refresh_token"]

    # The presented (now-rotated) refresh token must be rejected on reuse.
    reuse = await client.post("/auth/refresh", json={"refresh_token": refresh})
    assert reuse.status_code == 401
    assert reuse.json()["error"]["code"] == "authentication_failed"


async def test_refresh_rejects_garbage_401(client, db_session):
    resp = await client.post("/auth/refresh", json={"refresh_token": "garbage"})
    assert resp.status_code == 401
