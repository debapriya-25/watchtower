"""Watchlist request/response schemas (Pydantic v2)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.token import TokenPublic


# --------------------------------------------------------------------------- #
# Requests
# --------------------------------------------------------------------------- #
class WatchlistCreate(BaseModel):
    """Payload for ``POST /api/v1/watchlists``."""

    model_config = ConfigDict(
        json_schema_extra={"example": {"name": "DeFi blue chips"}}
    )

    name: str = Field(min_length=1, max_length=120)


class WatchlistUpdate(BaseModel):
    """Payload for ``PATCH /api/v1/watchlists/{id}`` (rename)."""

    model_config = ConfigDict(
        json_schema_extra={"example": {"name": "Long-term holds"}}
    )

    name: str = Field(min_length=1, max_length=120)


class WatchlistItemCreate(BaseModel):
    """Payload for ``POST /api/v1/watchlists/{id}/tokens``."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"token_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"}
        }
    )

    token_id: uuid.UUID = Field(description="Catalogue token id to add.")


# --------------------------------------------------------------------------- #
# Responses
# --------------------------------------------------------------------------- #
class WatchlistItemPublic(BaseModel):
    """A single token entry within a watchlist (with embedded token details)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    watchlist_id: uuid.UUID
    token_id: uuid.UUID
    created_at: datetime
    token: TokenPublic


class WatchlistSummary(BaseModel):
    """A watchlist without its items (used in list responses)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    item_count: int = Field(description="Number of tokens in this watchlist.")
    created_at: datetime
    updated_at: datetime


class WatchlistDetail(BaseModel):
    """A watchlist including its token items."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    items: list[WatchlistItemPublic]
    created_at: datetime
    updated_at: datetime


class WatchlistList(BaseModel):
    """A user's watchlists."""

    items: list[WatchlistSummary]
    total: int
