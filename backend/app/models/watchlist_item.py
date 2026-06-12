"""WatchlistItem ORM model.

A single tracked token within a watchlist. The token is referenced by its
CoinGecko ``coin_id`` (e.g. ``"bitcoin"``) plus a denormalised symbol; the full
token catalogue is a later phase, so no foreign key to a tokens catalogue table
is defined yet.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.watchlist import Watchlist


class WatchlistItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A token entry belonging to a watchlist."""

    __tablename__ = "watchlist_items"
    __table_args__ = (
        UniqueConstraint(
            "watchlist_id", "coin_id", name="uq_watchlist_item_coin"
        ),
    )

    watchlist_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("watchlists.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    coin_id: Mapped[str] = mapped_column(String(120), nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)

    watchlist: Mapped["Watchlist"] = relationship(back_populates="items")

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<WatchlistItem coin_id={self.coin_id!r} symbol={self.symbol!r}>"
