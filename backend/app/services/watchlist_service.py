"""Watchlist service: persistence, ownership enforcement and item management.

Every accessor that resolves a watchlist by id goes through
:func:`_get_owned_watchlist`, which raises:
  * :class:`NotFoundError` (404) if the watchlist does not exist, and
  * :class:`PermissionDeniedError` (403) if it belongs to another user.

This guarantees a user can never list, view, modify or delete another user's
watchlists.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, PermissionDeniedError
from app.core.logging import get_logger
from app.models.token import Token
from app.models.user import User
from app.models.watchlist import Watchlist
from app.models.watchlist_item import WatchlistItem

logger = get_logger(__name__)


# --------------------------------------------------------------------------- #
# Ownership-guarded lookups
# --------------------------------------------------------------------------- #
async def _get_owned_watchlist(
    db: AsyncSession, user: User, watchlist_id: uuid.UUID
) -> Watchlist:
    """Return the watchlist if it exists and is owned by ``user``.

    Raises 404 if missing, 403 if owned by someone else.
    """
    watchlist = await db.get(Watchlist, watchlist_id)
    if watchlist is None:
        raise NotFoundError("Watchlist not found.")
    if watchlist.user_id != user.id:
        logger.warning(
            "watchlist_ownership_denied",
            user_id=str(user.id),
            watchlist_id=str(watchlist_id),
            owner_id=str(watchlist.user_id),
        )
        raise PermissionDeniedError(
            "You do not have access to this watchlist."
        )
    return watchlist


async def _load_detail(
    db: AsyncSession, watchlist_id: uuid.UUID
) -> Watchlist:
    """Reload a watchlist with its items and each item's token eagerly loaded."""
    result = await db.execute(
        select(Watchlist)
        .where(Watchlist.id == watchlist_id)
        .options(selectinload(Watchlist.items).selectinload(WatchlistItem.token))
    )
    return result.scalar_one()


# --------------------------------------------------------------------------- #
# Watchlist CRUD
# --------------------------------------------------------------------------- #
async def create_watchlist(
    db: AsyncSession, user: User, *, name: str
) -> Watchlist:
    """Create a watchlist for ``user``; 409 if the name is already used."""
    existing = await db.scalar(
        select(Watchlist).where(
            Watchlist.user_id == user.id, Watchlist.name == name
        )
    )
    if existing is not None:
        raise ConflictError("You already have a watchlist with this name.")

    watchlist = Watchlist(user_id=user.id, name=name)
    db.add(watchlist)
    await db.flush()
    logger.info(
        "watchlist_created", user_id=str(user.id), watchlist_id=str(watchlist.id)
    )
    return await _load_detail(db, watchlist.id)


async def list_watchlists(
    db: AsyncSession, user: User
) -> list[tuple[Watchlist, int]]:
    """Return the caller's watchlists with their item counts."""
    result = await db.execute(
        select(Watchlist, func.count(WatchlistItem.id))
        .outerjoin(WatchlistItem, WatchlistItem.watchlist_id == Watchlist.id)
        .where(Watchlist.user_id == user.id)
        .group_by(Watchlist.id)
        .order_by(Watchlist.created_at.asc())
    )
    return [(row[0], int(row[1])) for row in result.all()]


async def get_watchlist(
    db: AsyncSession, user: User, watchlist_id: uuid.UUID
) -> Watchlist:
    """Return a single owned watchlist with items loaded."""
    await _get_owned_watchlist(db, user, watchlist_id)
    return await _load_detail(db, watchlist_id)


async def rename_watchlist(
    db: AsyncSession, user: User, watchlist_id: uuid.UUID, *, name: str
) -> Watchlist:
    """Rename an owned watchlist; 409 on a name clash with another of theirs."""
    watchlist = await _get_owned_watchlist(db, user, watchlist_id)

    if name != watchlist.name:
        clash = await db.scalar(
            select(Watchlist).where(
                Watchlist.user_id == user.id,
                Watchlist.name == name,
                Watchlist.id != watchlist_id,
            )
        )
        if clash is not None:
            raise ConflictError("You already have a watchlist with this name.")

    watchlist.name = name
    await db.flush()
    logger.info("watchlist_renamed", watchlist_id=str(watchlist_id))
    return await _load_detail(db, watchlist_id)


async def delete_watchlist(
    db: AsyncSession, user: User, watchlist_id: uuid.UUID
) -> None:
    """Delete an owned watchlist (items cascade)."""
    watchlist = await _get_owned_watchlist(db, user, watchlist_id)
    await db.delete(watchlist)
    await db.flush()
    logger.info("watchlist_deleted", watchlist_id=str(watchlist_id))


# --------------------------------------------------------------------------- #
# Watchlist token management
# --------------------------------------------------------------------------- #
async def add_token(
    db: AsyncSession,
    user: User,
    watchlist_id: uuid.UUID,
    *,
    token_id: uuid.UUID,
) -> WatchlistItem:
    """Add a catalogue token to an owned watchlist.

    Raises 404 if the watchlist or token does not exist, 409 if the token is
    already in the watchlist.
    """
    await _get_owned_watchlist(db, user, watchlist_id)

    token = await db.get(Token, token_id)
    if token is None:
        raise NotFoundError("Token not found.")

    duplicate = await db.scalar(
        select(WatchlistItem).where(
            WatchlistItem.watchlist_id == watchlist_id,
            WatchlistItem.token_id == token_id,
        )
    )
    if duplicate is not None:
        raise ConflictError("Token is already in this watchlist.")

    item = WatchlistItem(watchlist_id=watchlist_id, token=token)
    db.add(item)
    await db.flush()
    await db.refresh(item, attribute_names=["created_at"])
    logger.info(
        "watchlist_token_added",
        watchlist_id=str(watchlist_id),
        token_id=str(token_id),
    )
    return item


async def remove_token(
    db: AsyncSession,
    user: User,
    watchlist_id: uuid.UUID,
    token_id: uuid.UUID,
) -> None:
    """Remove a token from an owned watchlist; 404 if it is not present."""
    await _get_owned_watchlist(db, user, watchlist_id)

    item = await db.scalar(
        select(WatchlistItem).where(
            WatchlistItem.watchlist_id == watchlist_id,
            WatchlistItem.token_id == token_id,
        )
    )
    if item is None:
        raise NotFoundError("Token is not in this watchlist.")

    await db.delete(item)
    await db.flush()
    logger.info(
        "watchlist_token_removed",
        watchlist_id=str(watchlist_id),
        token_id=str(token_id),
    )
