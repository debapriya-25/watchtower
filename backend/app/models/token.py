"""Token ORM model — the crypto-asset catalogue.

An admin-managed catalogue of crypto tokens, seeded from the CoinGecko
top-by-market-cap list. Watchlist items and alerts (later phases) reference a
catalogue token by its ``coingecko_id``.

Not to be confused with :class:`app.models.refresh_token.RefreshToken`, which is
the authentication refresh token.
"""

from __future__ import annotations

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Token(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A crypto token in the global catalogue."""

    __tablename__ = "tokens"

    symbol: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    coingecko_id: Mapped[str] = mapped_column(
        String(120), unique=True, index=True, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, index=True
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return (
            f"<Token symbol={self.symbol!r} coingecko_id={self.coingecko_id!r} "
            f"is_active={self.is_active}>"
        )
