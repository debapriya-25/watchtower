"""Watchlist management routes (``/api/v1/watchlists``).

All routes require authentication and are strictly **owner-scoped**: a user can
only ever see or mutate their own watchlists. Attempting to touch another user's
watchlist returns **403**.

* ``POST   /api/v1/watchlists``                         — create
* ``GET    /api/v1/watchlists``                         — list (caller's own)
* ``GET    /api/v1/watchlists/{id}``                    — retrieve one
* ``PATCH  /api/v1/watchlists/{id}``                    — rename
* ``DELETE /api/v1/watchlists/{id}``                    — delete
* ``POST   /api/v1/watchlists/{id}/tokens``             — add a token
* ``DELETE /api/v1/watchlists/{id}/tokens/{token_id}``  — remove a token
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Path, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.responses import success_response
from app.db.session import get_db
from app.deps.auth import CurrentUser
from app.schemas.common import Envelope, ErrorEnvelope, MessageData
from app.schemas.watchlist import (
    WatchlistCreate,
    WatchlistDetail,
    WatchlistItemCreate,
    WatchlistItemPublic,
    WatchlistList,
    WatchlistSummary,
    WatchlistUpdate,
)
from app.services import watchlist_service

router = APIRouter(prefix="/api/v1/watchlists", tags=["watchlists"])

DbSession = Annotated[AsyncSession, Depends(get_db)]

WatchlistIdPath = Annotated[uuid.UUID, Path(description="Watchlist id")]

_AUTH_RESPONSES = {
    401: {"model": ErrorEnvelope, "description": "Authentication required"},
}
_OWNED_RESPONSES = {
    **_AUTH_RESPONSES,
    403: {"model": ErrorEnvelope, "description": "Watchlist belongs to another user"},
    404: {"model": ErrorEnvelope, "description": "Watchlist not found"},
}


def _detail(watchlist) -> dict:
    return WatchlistDetail.model_validate(watchlist).model_dump()


# --------------------------------------------------------------------------- #
# Watchlist CRUD
# --------------------------------------------------------------------------- #
@router.post(
    "",
    response_model=Envelope[WatchlistDetail],
    status_code=status.HTTP_201_CREATED,
    summary="Create a watchlist",
    description="Creates a new, empty watchlist owned by the current user. "
    "Watchlist names must be unique per user.",
    responses={
        **_AUTH_RESPONSES,
        409: {"model": ErrorEnvelope, "description": "Duplicate watchlist name"},
    },
)
async def create_watchlist(
    current_user: CurrentUser,
    db: DbSession,
    payload: WatchlistCreate,
) -> JSONResponse:
    watchlist = await watchlist_service.create_watchlist(
        db, current_user, name=payload.name
    )
    return success_response(
        data=_detail(watchlist), status_code=status.HTTP_201_CREATED
    )


@router.get(
    "",
    response_model=Envelope[WatchlistList],
    summary="List my watchlists",
    description="Returns the current user's watchlists (with token counts). "
    "Never includes other users' watchlists.",
    responses=_AUTH_RESPONSES,
)
async def list_watchlists(
    current_user: CurrentUser,
    db: DbSession,
) -> JSONResponse:
    rows = await watchlist_service.list_watchlists(db, current_user)
    items = [
        WatchlistSummary(
            id=w.id,
            user_id=w.user_id,
            name=w.name,
            item_count=count,
            created_at=w.created_at,
            updated_at=w.updated_at,
        )
        for w, count in rows
    ]
    data = WatchlistList(items=items, total=len(items))
    return success_response(data=data.model_dump())


@router.get(
    "/{watchlist_id}",
    response_model=Envelope[WatchlistDetail],
    summary="Get one of my watchlists",
    description="Returns a single watchlist (with its tokens). Returns 403 if "
    "the watchlist belongs to another user, 404 if it does not exist.",
    responses=_OWNED_RESPONSES,
)
async def get_watchlist(
    current_user: CurrentUser,
    db: DbSession,
    watchlist_id: WatchlistIdPath,
) -> JSONResponse:
    watchlist = await watchlist_service.get_watchlist(
        db, current_user, watchlist_id
    )
    return success_response(data=_detail(watchlist))


@router.patch(
    "/{watchlist_id}",
    response_model=Envelope[WatchlistDetail],
    summary="Rename a watchlist",
    description="Renames an owned watchlist. Returns 403 for another user's "
    "watchlist, 409 on a duplicate name.",
    responses={
        **_OWNED_RESPONSES,
        409: {"model": ErrorEnvelope, "description": "Duplicate watchlist name"},
    },
)
async def update_watchlist(
    current_user: CurrentUser,
    db: DbSession,
    payload: WatchlistUpdate,
    watchlist_id: WatchlistIdPath,
) -> JSONResponse:
    watchlist = await watchlist_service.rename_watchlist(
        db, current_user, watchlist_id, name=payload.name
    )
    return success_response(data=_detail(watchlist))


@router.delete(
    "/{watchlist_id}",
    response_model=Envelope[MessageData],
    summary="Delete a watchlist",
    description="Deletes an owned watchlist and all of its token items. "
    "Returns 403 for another user's watchlist.",
    responses=_OWNED_RESPONSES,
)
async def delete_watchlist(
    current_user: CurrentUser,
    db: DbSession,
    watchlist_id: WatchlistIdPath,
) -> JSONResponse:
    await watchlist_service.delete_watchlist(db, current_user, watchlist_id)
    return success_response(data={"message": "Watchlist deleted."})


# --------------------------------------------------------------------------- #
# Watchlist token management
# --------------------------------------------------------------------------- #
@router.post(
    "/{watchlist_id}/tokens",
    response_model=Envelope[WatchlistItemPublic],
    status_code=status.HTTP_201_CREATED,
    summary="Add a token to a watchlist",
    description="Adds a catalogue token to an owned watchlist. The token must "
    "exist in the catalogue (404 otherwise) and may not already be present "
    "(409 otherwise).",
    responses={
        **_OWNED_RESPONSES,
        404: {"model": ErrorEnvelope, "description": "Watchlist or token not found"},
        409: {"model": ErrorEnvelope, "description": "Token already in watchlist"},
    },
)
async def add_token(
    current_user: CurrentUser,
    db: DbSession,
    payload: WatchlistItemCreate,
    watchlist_id: WatchlistIdPath,
) -> JSONResponse:
    item = await watchlist_service.add_token(
        db, current_user, watchlist_id, token_id=payload.token_id
    )
    return success_response(
        data=WatchlistItemPublic.model_validate(item).model_dump(),
        status_code=status.HTTP_201_CREATED,
    )


@router.delete(
    "/{watchlist_id}/tokens/{token_id}",
    response_model=Envelope[MessageData],
    summary="Remove a token from a watchlist",
    description="Removes a token from an owned watchlist. Returns 404 if the "
    "token is not in the watchlist.",
    responses={
        **_OWNED_RESPONSES,
        404: {"model": ErrorEnvelope, "description": "Watchlist or token not found"},
    },
)
async def remove_token(
    current_user: CurrentUser,
    db: DbSession,
    watchlist_id: WatchlistIdPath,
    token_id: Annotated[uuid.UUID, Path(description="Catalogue token id")],
) -> JSONResponse:
    await watchlist_service.remove_token(
        db, current_user, watchlist_id, token_id
    )
    return success_response(data={"message": "Token removed from watchlist."})
