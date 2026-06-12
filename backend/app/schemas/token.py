"""Token catalogue request/response schemas (Pydantic v2)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TokenPublic(BaseModel):
    """Public representation of a catalogue token."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    symbol: str
    name: str
    coingecko_id: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class TokenCreate(BaseModel):
    """Payload for ``POST /api/v1/tokens`` (admin)."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "symbol": "BTC",
                "name": "Bitcoin",
                "coingecko_id": "bitcoin",
                "is_active": True,
            }
        }
    )

    symbol: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=120)
    coingecko_id: str = Field(min_length=1, max_length=120)
    is_active: bool = True


class TokenUpdate(BaseModel):
    """Partial update for ``PATCH /api/v1/tokens/{id}`` (admin).

    Only the provided fields are changed. ``coingecko_id`` is immutable (it is
    the external identity) and therefore not updatable here.
    """

    model_config = ConfigDict(
        json_schema_extra={"example": {"is_active": False}}
    )

    symbol: str | None = Field(default=None, min_length=1, max_length=32)
    name: str | None = Field(default=None, min_length=1, max_length=120)
    is_active: bool | None = None


class PageMeta(BaseModel):
    """Pagination metadata for list endpoints."""

    page: int
    size: int
    total: int
    pages: int


class TokenList(BaseModel):
    """A page of catalogue tokens."""

    items: list[TokenPublic]
    pagination: PageMeta


class TokenPrice(BaseModel):
    """Live (cached) price for a single token."""

    token_id: uuid.UUID
    symbol: str
    coingecko_id: str
    currency: str
    price: float
    cached: bool = Field(
        description="True if served from the Redis cache, False if freshly "
        "fetched from CoinGecko."
    )
    fetched_at: datetime
