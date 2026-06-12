"""Token catalogue service: DB access + read-through price cache.

Keeps the routers thin. All catalogue persistence and the Redis/CoinGecko
price-resolution flow live here.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ConflictError, NotFoundError
from app.core.logging import get_logger
from app.models.token import Token
from app.services import coingecko

logger = get_logger(__name__)


def _price_cache_key(coingecko_id: str, currency: str) -> str:
    return f"price:{coingecko_id}:{currency}"


# --------------------------------------------------------------------------- #
# Catalogue queries
# --------------------------------------------------------------------------- #
async def list_active_tokens(
    db: AsyncSession, *, page: int, size: int
) -> tuple[list[Token], int]:
    """Return a page of active tokens plus the total active count."""
    offset = (page - 1) * size

    total = await db.scalar(
        select(func.count()).select_from(Token).where(Token.is_active.is_(True))
    )
    result = await db.execute(
        select(Token)
        .where(Token.is_active.is_(True))
        .order_by(Token.symbol.asc())
        .offset(offset)
        .limit(size)
    )
    return list(result.scalars().all()), int(total or 0)


async def get_token(db: AsyncSession, token_id: uuid.UUID) -> Token:
    """Return a token by id or raise :class:`NotFoundError`."""
    token = await db.get(Token, token_id)
    if token is None:
        raise NotFoundError("Token not found.")
    return token


async def get_token_by_coingecko_id(
    db: AsyncSession, coingecko_id: str
) -> Token | None:
    result = await db.execute(
        select(Token).where(Token.coingecko_id == coingecko_id)
    )
    return result.scalar_one_or_none()


async def create_token(
    db: AsyncSession,
    *,
    symbol: str,
    name: str,
    coingecko_id: str,
    is_active: bool = True,
) -> Token:
    """Create a catalogue token; 409 if the coingecko_id already exists."""
    if await get_token_by_coingecko_id(db, coingecko_id) is not None:
        raise ConflictError(
            f"A token with coingecko_id '{coingecko_id}' already exists."
        )

    token = Token(
        symbol=symbol.upper(),
        name=name,
        coingecko_id=coingecko_id,
        is_active=is_active,
    )
    db.add(token)
    await db.flush()
    await db.refresh(token)
    logger.info("token_created", coingecko_id=coingecko_id, symbol=token.symbol)
    return token


async def update_token(
    db: AsyncSession,
    token_id: uuid.UUID,
    *,
    fields: dict[str, Any],
) -> Token:
    """Apply a partial update to a catalogue token."""
    token = await get_token(db, token_id)

    if "symbol" in fields and fields["symbol"] is not None:
        token.symbol = fields["symbol"].upper()
    if "name" in fields and fields["name"] is not None:
        token.name = fields["name"]
    if "is_active" in fields and fields["is_active"] is not None:
        token.is_active = fields["is_active"]

    await db.flush()
    await db.refresh(token)
    logger.info(
        "token_updated", token_id=str(token_id), is_active=token.is_active
    )
    return token


# --------------------------------------------------------------------------- #
# Read-through price cache
# --------------------------------------------------------------------------- #
async def get_token_price(
    redis: Redis, token: Token, *, currency: str | None = None
) -> dict[str, Any]:
    """Resolve a token's price using a read-through Redis cache.

    Flow: check Redis -> on hit return cached payload (``cached=True``);
    on miss call CoinGecko, store under ``PRICE_CACHE_TTL_SEC``, and return
    (``cached=False``).
    """
    currency = currency or settings.price_vs_currency
    key = _price_cache_key(token.coingecko_id, currency)

    cached_raw = await redis.get(key)
    if cached_raw is not None:
        payload = json.loads(cached_raw)
        payload["cached"] = True
        logger.info("price_cache_hit", coingecko_id=token.coingecko_id)
        return payload

    # Cache miss -> fetch live, then populate the cache.
    price = await coingecko.get_token_price(token.coingecko_id, currency)
    payload = {
        "token_id": str(token.id),
        "symbol": token.symbol,
        "coingecko_id": token.coingecko_id,
        "currency": currency,
        "price": price,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
    # Store without the volatile ``cached`` flag.
    await redis.set(key, json.dumps(payload), ex=settings.price_cache_ttl_sec)
    payload["cached"] = False
    logger.info("price_cache_miss", coingecko_id=token.coingecko_id, price=price)
    return payload
