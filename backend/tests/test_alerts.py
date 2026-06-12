"""Phase 4 price-alert tests.

Covered: create, list, ownership protection, activate, deactivate, ABOVE
trigger, BELOW trigger, auto-disable after trigger, invalid token, invalid
target price.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.token import Token

pytestmark = pytest.mark.asyncio

BASE = "/api/v1/alerts"


async def _make_token(db: AsyncSession, *, symbol: str = "BTC") -> Token:
    token = Token(
        symbol=symbol,
        name=f"{symbol} coin",
        coingecko_id=f"test-{uuid.uuid4().hex}",
        is_active=True,
    )
    db.add(token)
    await db.flush()
    return token


async def _create_alert(client, headers, token_id, *, condition="ABOVE", price=100.0):
    return await client.post(
        BASE,
        json={"token_id": str(token_id), "condition": condition, "target_price": price},
        headers=headers,
    )


# --------------------------------------------------------------------------- #
# CRUD endpoints
# --------------------------------------------------------------------------- #
async def test_create_alert(client, db_session, user_auth):
    token = await _make_token(db_session)
    resp = await _create_alert(client, user_auth, token.id, condition="ABOVE", price=75000.0)
    assert resp.status_code == 201

    data = resp.json()["data"]
    assert data["token_id"] == str(token.id)
    assert data["condition"] == "ABOVE"
    assert data["target_price"] == 75000.0
    assert data["is_active"] is True
    assert data["triggered_at"] is None
    assert data["token"]["symbol"] == "BTC"


async def test_create_alert_invalid_token_returns_404(client, user_auth):
    resp = await _create_alert(client, user_auth, uuid.uuid4())
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"


async def test_create_alert_invalid_target_price_returns_422(client, db_session, user_auth):
    token = await _make_token(db_session)
    for bad in (0, -5):
        resp = await _create_alert(client, user_auth, token.id, price=bad)
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "validation_error"


async def test_list_alerts(client, db_session, user_auth):
    token = await _make_token(db_session)
    await _create_alert(client, user_auth, token.id, condition="ABOVE", price=100)
    await _create_alert(client, user_auth, token.id, condition="BELOW", price=50)

    resp = await client.get(BASE, headers=user_auth)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total"] == 2
    assert {a["condition"] for a in data["items"]} == {"ABOVE", "BELOW"}


async def test_list_only_returns_own_alerts(client, db_session, user_auth, other_user_auth):
    token = await _make_token(db_session)
    await _create_alert(client, user_auth, token.id)
    await _create_alert(client, other_user_auth, token.id)

    resp = await client.get(BASE, headers=user_auth)
    assert resp.json()["data"]["total"] == 1


# --------------------------------------------------------------------------- #
# Ownership protection
# --------------------------------------------------------------------------- #
async def test_ownership_enforced(client, db_session, user_auth, other_user_auth):
    token = await _make_token(db_session)
    aid = (await _create_alert(client, user_auth, token.id)).json()["data"]["id"]

    get_r = await client.get(f"{BASE}/{aid}", headers=other_user_auth)
    patch_r = await client.patch(
        f"{BASE}/{aid}", json={"target_price": 1}, headers=other_user_auth
    )
    del_r = await client.delete(f"{BASE}/{aid}", headers=other_user_auth)
    act_r = await client.post(f"{BASE}/{aid}/activate", headers=other_user_auth)

    for resp in (get_r, patch_r, del_r, act_r):
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "permission_denied"


async def test_missing_alert_returns_404(client, user_auth):
    resp = await client.get(f"{BASE}/{uuid.uuid4()}", headers=user_auth)
    assert resp.status_code == 404


# --------------------------------------------------------------------------- #
# Activate / deactivate
# --------------------------------------------------------------------------- #
async def test_deactivate_then_activate(client, db_session, user_auth):
    token = await _make_token(db_session)
    aid = (await _create_alert(client, user_auth, token.id)).json()["data"]["id"]

    deact = await client.post(f"{BASE}/{aid}/deactivate", headers=user_auth)
    assert deact.status_code == 200
    assert deact.json()["data"]["is_active"] is False

    act = await client.post(f"{BASE}/{aid}/activate", headers=user_auth)
    assert act.status_code == 200
    assert act.json()["data"]["is_active"] is True
    assert act.json()["data"]["triggered_at"] is None


async def test_delete_alert(client, db_session, user_auth):
    token = await _make_token(db_session)
    aid = (await _create_alert(client, user_auth, token.id)).json()["data"]["id"]

    assert (await client.delete(f"{BASE}/{aid}", headers=user_auth)).status_code == 200
    assert (await client.get(f"{BASE}/{aid}", headers=user_auth)).status_code == 404
