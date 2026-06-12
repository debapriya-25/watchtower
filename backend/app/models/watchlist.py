"""Watchlist ORM model.

A watchlist belongs to exactly one user; ownership is enforced in the service
layer. ``UNIQUE(user_id, name)`` prevents a single user from creating two
watchlists with the same name.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.watchlist_item import WatchlistItem


class Watchlist(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A named collection of tokens owned by a user."""

    __tablename__ = "watchlists"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_watchlist_user_name"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)

    user: Mapped["User"] = relationship(back_populates="watchlists")
    items: Mapped[list["WatchlistItem"]] = relationship(
        back_populates="watchlist",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="WatchlistItem.created_at",
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Watchlist id={self.id!s} name={self.name!r}>"
