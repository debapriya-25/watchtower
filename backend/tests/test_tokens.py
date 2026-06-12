"""Phase 2 token-catalogue endpoint tests.

Covered: token listing, price cache hit, price cache miss, admin token
creation, and the user-forbidden (403) path.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.token import Token
from app.services import coingecko

pytestmark = pytest.mark.asyncio


async def _seed_catalogue(db: AsyncSession) -> dict[str, Token]:
    """Replace catalogue (within the rolled-back txn) with 2 active + 1 inactive."""
    await db.execute(delete(Token))
    btc = Token(symbol="BTC", name="Bitcoin", coingecko_id="bitcoin", is_active=True)
    eth = Token(symbol="ETH", name="Ethereum", coingecko_id="ethereum", is_active=True)
    old = Token(symbol="OLD", name="Old Coin", coingecko_id="oldcoin", is_active=False)
    db.add_all([btc, eth, old])
    await db.flush()
    return {"btc": btc, "eth": eth, "old": old}


# --------------------------------------------------------------------------- #
# Listing
# --------------------------------------------------------------------------- #
async def test_list_tokens_returns_active_only_paginated(
    client, db_session, user_auth
):
    await _seed_catalogue(db_session)

    resp = await client.get("/api/v1/tokens", params={"page": 1, "size": 10}, headers=user_auth)
    assert resp.status_code == 200

    body = resp.json()
    assert body["success"] is True
    assert body["error"] is None

    data = body["data"]
    symbols = {item["symbol"] for item in data["items"]}
    assert symbols == {"BTC", "ETH"}  # inactive OLD excluded
    assert all(item["is_active"] for item in data["items"])

    assert data["pagination"] == {"page": 1, "size": 10, "total": 2, "pages": 1}


async def test_list_tokens_requires_authentication(client, db_session):
    await _seed_catalogue(db_session)
    resp = await client.get("/api/v1/tokens")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "authentication_failed"


# --------------------------------------------------------------------------- #
# Price cache (miss / hit)
# --------------------------------------------------------------------------- #
async def test_price_cache_miss_calls_coingecko(
    client, db_session, user_auth, fake_redis, monkeypatch
):
    tokens = await _seed_catalogue(db_session)
    calls: list[str] = []

    async def fake_get_price(coingecko_id: str, vs_currency: str | None = None) -> float:
        calls.append(coingecko_id)
        return 12345.67

    monkeypatch.setattr(coingecko, "get_token_price", fake_get_price)

    resp = await client.get(
        f"/api/v1/tokens/{tokens['btc'].id}/price", headers=user_auth
    )
    assert resp.status_code == 200

    data = resp.json()["data"]
    assert data["cached"] is False
    assert data["price"] == 12345.67
    assert data["symbol"] == "BTC"
    assert len(calls) == 1  # CoinGecko hit exactly once
    # Value was written to the cache.
    assert fake_redis.store  # non-empty


async def test_price_cache_hit_skips_coingecko(
    client, db_session, user_auth, fake_redis, monkeypatch
):
    tokens = await _seed_catalogue(db_session)
    calls: list[str] = []

    async def fake_get_price(coingecko_id: str, vs_currency: str | None = None) -> float:
        calls.append(coingecko_id)
        return 999.0

    monkeypatch.setattr(coingecko, "get_token_price", fake_get_price)

    url = f"/api/v1/tokens/{tokens['eth'].id}/price"
    first = await client.get(url, headers=user_auth)
    second = await client.get(url, headers=user_auth)

    assert first.status_code == second.status_code == 200
    assert first.json()["data"]["cached"] is False
    assert second.json()["data"]["cached"] is True
    assert second.json()["data"]["price"] == 999.0
    assert len(calls) == 1  # second request served from cache


async def test_price_unknown_token_returns_404(client, db_session, user_auth):
    await _seed_catalogue(db_session)
    resp = await client.get(
        f"/api/v1/tokens/{uuid.uuid4()}/price", headers=user_auth
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"


# --------------------------------------------------------------------------- #
# Admin protection
# --------------------------------------------------------------------------- #
async def test_admin_can_create_token(client, db_session, admin_auth):
    await db_session.execute(delete(Token))

    resp = await client.post(
        "/api/v1/tokens",
        json={"symbol": "sol", "name": "Solana", "coingecko_id": "solana"},
        headers=admin_auth,
    )
    assert resp.status_code == 201

    data = resp.json()["data"]
    assert data["symbol"] == "SOL"  # normalised to upper-case
    assert data["coingecko_id"] == "solana"
    assert data["is_active"] is True


async def test_user_cannot_create_token(client, db_session, user_auth):
    resp = await client.post(
        "/api/v1/tokens",
        json={"symbol": "SOL", "name": "Solana", "coingecko_id": "solana"},
        headers=user_auth,
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "permission_denied"


async def test_admin_can_deactivate_token(client, db_session, admin_auth):
    tokens = await _seed_catalogue(db_session)
    resp = await client.patch(
        f"/api/v1/tokens/{tokens['btc'].id}",
        json={"is_active": False},
        headers=admin_auth,
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["is_active"] is False
