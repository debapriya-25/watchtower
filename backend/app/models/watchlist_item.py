"""WatchlistItem ORM model.

A single catalogue token tracked within a watchlist. The token is referenced by
a foreign key to the Phase 2 catalogue (:class:`app.models.token.Token`).
``UNIQUE(watchlist_id, token_id)`` guarantees a token appears at most once in a
given watchlist.

Items are immutable once created (a token is either present or removed), so the
model carries only ``created_at`` — no ``updated_at``.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.token import Token
    from app.models.watchlist import Watchlist


class WatchlistItem(UUIDPrimaryKeyMixin, Base):
    """A catalogue token belonging to a watchlist."""

    __tablename__ = "watchlist_items"
    __table_args__ = (
        UniqueConstraint(
            "watchlist_id", "token_id", name="uq_watchlist_item_token"
        ),
    )

    watchlist_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("watchlists.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    token_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tokens.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    watchlist: Mapped["Watchlist"] = relationship(back_populates="items")
    token: Mapped["Token"] = relationship(lazy="raise")

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return (
            f"<WatchlistItem watchlist_id={self.watchlist_id!s} "
            f"token_id={self.token_id!s}>"
        )
