"""Phase 3 watchlist-management endpoint tests.

Covered: create, list, ownership enforcement (403), add token, duplicate
prevention, remove token, delete watchlist — plus token-must-exist validation.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.token import Token

pytestmark = pytest.mark.asyncio

BASE = "/api/v1/watchlists"


async def _make_token(db: AsyncSession, *, symbol: str) -> Token:
    # Unique coingecko_id avoids colliding with the committed seed catalogue.
    token = Token(
        symbol=symbol,
        name=f"{symbol} coin",
        coingecko_id=f"test-{uuid.uuid4().hex}",
        is_active=True,
    )
    db.add(token)
    await db.flush()
    return token


async def _create_watchlist(client, headers, name: str) -> dict:
    resp = await client.post(BASE, json={"name": name}, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


# --------------------------------------------------------------------------- #
# Create / list
# --------------------------------------------------------------------------- #
async def test_create_watchlist(client, user_auth):
    resp = await client.post(BASE, json={"name": "DeFi"}, headers=user_auth)
    assert resp.status_code == 201

    body = resp.json()
    assert body["success"] is True and body["error"] is None
    data = body["data"]
    assert data["name"] == "DeFi"
    assert data["items"] == []
    assert uuid.UUID(data["id"])  # valid uuid
    assert uuid.UUID(data["user_id"])


async def test_create_watchlist_requires_auth(client):
    resp = await client.post(BASE, json={"name": "Nope"})
    assert resp.status_code == 401


async def test_duplicate_watchlist_name_rejected(client, user_auth):
    await _create_watchlist(client, user_auth, "Same")
    resp = await client.post(BASE, json={"name": "Same"}, headers=user_auth)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "conflict"


async def test_list_watchlists(client, user_auth):
    await _create_watchlist(client, user_auth, "One")
    await _create_watchlist(client, user_auth, "Two")

    resp = await client.get(BASE, headers=user_auth)
    assert resp.status_code == 200

    data = resp.json()["data"]
    assert data["total"] == 2
    names = {w["name"] for w in data["items"]}
    assert names == {"One", "Two"}
    assert all(w["item_count"] == 0 for w in data["items"])


async def test_list_only_returns_own_watchlists(client, user_auth, other_user_auth):
    await _create_watchlist(client, user_auth, "Mine")
    await _create_watchlist(client, other_user_auth, "Theirs")

    resp = await client.get(BASE, headers=user_auth)
    data = resp.json()["data"]
    assert data["total"] == 1
    assert data["items"][0]["name"] == "Mine"


# --------------------------------------------------------------------------- #
# Ownership enforcement (403)
# --------------------------------------------------------------------------- #
async def test_ownership_enforced_across_endpoints(
    client, user_auth, other_user_auth
):
    wl = await _create_watchlist(client, user_auth, "Private")
    wid = wl["id"]

    # Another user cannot view, rename, or delete it.
    get_resp = await client.get(f"{BASE}/{wid}", headers=other_user_auth)
    patch_resp = await client.patch(
        f"{BASE}/{wid}", json={"name": "Hacked"}, headers=other_user_auth
    )
    delete_resp = await client.delete(f"{BASE}/{wid}", headers=other_user_auth)

    for resp in (get_resp, patch_resp, delete_resp):
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "permission_denied"


async def test_missing_watchlist_returns_404(client, user_auth):
    resp = await client.get(f"{BASE}/{uuid.uuid4()}", headers=user_auth)
    assert resp.status_code == 404


# --------------------------------------------------------------------------- #
# Token management
# --------------------------------------------------------------------------- #
async def test_add_token(client, db_session, user_auth):
    token = await _make_token(db_session, symbol="BTC")
    wl = await _create_watchlist(client, user_auth, "Crypto")

    resp = await client.post(
        f"{BASE}/{wl['id']}/tokens",
        json={"token_id": str(token.id)},
        headers=user_auth,
    )
    assert resp.status_code == 201

    item = resp.json()["data"]
    assert item["token_id"] == str(token.id)
    assert item["token"]["symbol"] == "BTC"

    # It now shows up in the watchlist detail.
    detail = (await client.get(f"{BASE}/{wl['id']}", headers=user_auth)).json()["data"]
    assert len(detail["items"]) == 1


async def test_add_nonexistent_token_returns_404(client, user_auth):
    wl = await _create_watchlist(client, user_auth, "Empty")
    resp = await client.post(
        f"{BASE}/{wl['id']}/tokens",
        json={"token_id": str(uuid.uuid4())},
        headers=user_auth,
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"


async def test_duplicate_token_prevented(client, db_session, user_auth):
    token = await _make_token(db_session, symbol="ETH")
    wl = await _create_watchlist(client, user_auth, "Dupes")

    first = await client.post(
        f"{BASE}/{wl['id']}/tokens",
        json={"token_id": str(token.id)},
        headers=user_auth,
    )
    second = await client.post(
        f"{BASE}/{wl['id']}/tokens",
        json={"token_id": str(token.id)},
        headers=user_auth,
    )
    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "conflict"


async def test_remove_token(client, db_session, user_auth):
    token = await _make_token(db_session, symbol="SOL")
    wl = await _create_watchlist(client, user_auth, "Removable")
    await client.post(
        f"{BASE}/{wl['id']}/tokens",
        json={"token_id": str(token.id)},
        headers=user_auth,
    )

    resp = await client.delete(
        f"{BASE}/{wl['id']}/tokens/{token.id}", headers=user_auth
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True

    detail = (await client.get(f"{BASE}/{wl['id']}", headers=user_auth)).json()["data"]
    assert detail["items"] == []


async def test_remove_token_not_in_watchlist_returns_404(
    client, db_session, user_auth
):
    wl = await _create_watchlist(client, user_auth, "NoToken")
    resp = await client.delete(
        f"{BASE}/{wl['id']}/tokens/{uuid.uuid4()}", headers=user_auth
    )
    assert resp.status_code == 404


async def test_cannot_add_token_to_others_watchlist(
    client, db_session, user_auth, other_user_auth
):
    token = await _make_token(db_session, symbol="ADA")
    wl = await _create_watchlist(client, user_auth, "Owner only")

    resp = await client.post(
        f"{BASE}/{wl['id']}/tokens",
        json={"token_id": str(token.id)},
        headers=other_user_auth,
    )
    assert resp.status_code == 403


# --------------------------------------------------------------------------- #
# Rename / delete
# --------------------------------------------------------------------------- #
async def test_rename_watchlist(client, user_auth):
    wl = await _create_watchlist(client, user_auth, "Old name")
    resp = await client.patch(
        f"{BASE}/{wl['id']}", json={"name": "New name"}, headers=user_auth
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["name"] == "New name"


async def test_delete_watchlist(client, user_auth):
    wl = await _create_watchlist(client, user_auth, "Throwaway")

    delete_resp = await client.delete(f"{BASE}/{wl['id']}", headers=user_auth)
    assert delete_resp.status_code == 200

    get_resp = await client.get(f"{BASE}/{wl['id']}", headers=user_auth)
    assert get_resp.status_code == 404
