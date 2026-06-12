"""Token catalogue & live price routes (``/api/v1/tokens``).

* ``GET    /api/v1/tokens``            — list active tokens (any authenticated user)
* ``GET    /api/v1/tokens/{id}/price`` — live, Redis-cached price
* ``POST   /api/v1/tokens``            — add a token (admin only)
* ``PATCH  /api/v1/tokens/{id}``       — update a token (admin only)
"""

from __future__ import annotations

import math
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, status
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.responses import success_response
from app.db.redis import get_redis
from app.db.session import get_db
from app.deps.auth import AdminUser, CurrentUser
from app.schemas.common import Envelope, ErrorEnvelope
from app.schemas.token import (
    PageMeta,
    TokenCreate,
    TokenList,
    TokenPrice,
    TokenPublic,
    TokenUpdate,
)
from app.services import token_service

router = APIRouter(prefix="/api/v1/tokens", tags=["tokens"])

DbSession = Annotated[AsyncSession, Depends(get_db)]
RedisDep = Annotated[Redis, Depends(get_redis)]

_AUTH_RESPONSES = {
    401: {"model": ErrorEnvelope, "description": "Authentication required"},
}
_ADMIN_RESPONSES = {
    **_AUTH_RESPONSES,
    403: {"model": ErrorEnvelope, "description": "Administrator privileges required"},
}


@router.get(
    "",
    response_model=Envelope[TokenList],
    summary="List active catalogue tokens",
    description=(
        "Returns a paginated list of **active** catalogue tokens, ordered by "
        "symbol. Available to any authenticated user."
    ),
    responses=_AUTH_RESPONSES,
)
async def list_tokens(
    current_user: CurrentUser,
    db: DbSession,
    page: Annotated[int, Query(ge=1, description="1-based page number")] = 1,
    size: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 20,
) -> JSONResponse:
    items, total = await token_service.list_active_tokens(db, page=page, size=size)
    data = TokenList(
        items=[TokenPublic.model_validate(t) for t in items],
        pagination=PageMeta(
            page=page,
            size=size,
            total=total,
            pages=math.ceil(total / size) if size else 0,
        ),
    )
    return success_response(data=data.model_dump())


@router.get(
    "/{token_id}/price",
    response_model=Envelope[TokenPrice],
    summary="Get a token's live (cached) price",
    description=(
        "Resolves the token's current price through a **read-through Redis "
        "cache**. On a cache hit the cached value is returned with "
        "`cached=true`; on a miss the price is fetched from CoinGecko, cached "
        "for `PRICE_CACHE_TTL_SEC` seconds, and returned with `cached=false`."
    ),
    responses={
        **_AUTH_RESPONSES,
        404: {"model": ErrorEnvelope, "description": "Token not found"},
        502: {"model": ErrorEnvelope, "description": "Upstream price provider error"},
    },
)
async def get_token_price(
    current_user: CurrentUser,
    db: DbSession,
    redis: RedisDep,
    token_id: Annotated[uuid.UUID, Path(description="Catalogue token id")],
) -> JSONResponse:
    token = await token_service.get_token(db, token_id)
    payload = await token_service.get_token_price(redis, token)
    return success_response(data=TokenPrice(**payload).model_dump())


@router.post(
    "",
    response_model=Envelope[TokenPublic],
    status_code=status.HTTP_201_CREATED,
    summary="Add a token to the catalogue (admin only)",
    responses={
        **_ADMIN_RESPONSES,
        409: {"model": ErrorEnvelope, "description": "coingecko_id already exists"},
    },
)
async def create_token(
    admin: AdminUser,
    db: DbSession,
    payload: TokenCreate,
) -> JSONResponse:
    token = await token_service.create_token(
        db,
        symbol=payload.symbol,
        name=payload.name,
        coingecko_id=payload.coingecko_id,
        is_active=payload.is_active,
    )
    return success_response(
        data=TokenPublic.model_validate(token).model_dump(),
        status_code=status.HTTP_201_CREATED,
    )


@router.patch(
    "/{token_id}",
    response_model=Envelope[TokenPublic],
    summary="Update a catalogue token (admin only)",
    responses={
        **_ADMIN_RESPONSES,
        404: {"model": ErrorEnvelope, "description": "Token not found"},
    },
)
async def update_token(
    admin: AdminUser,
    db: DbSession,
    payload: TokenUpdate,
    token_id: Annotated[uuid.UUID, Path(description="Catalogue token id")],
) -> JSONResponse:
    token = await token_service.update_token(
        db, token_id, fields=payload.model_dump(exclude_unset=True)
    )
    return success_response(data=TokenPublic.model_validate(token).model_dump())
