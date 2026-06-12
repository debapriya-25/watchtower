"""Refresh-token ORM model.

One row is persisted per issued refresh token. Tokens are referenced by their
``jti`` (JWT ID) so they can be revoked server-side (logout, rotation, or
security events) without trusting only the token's own expiry claim.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.user import User


class Token(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A persisted, revocable refresh token."""

    __tablename__ = "tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    jti: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    revoked: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="tokens")

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Token jti={self.jti!r} user_id={self.user_id!s} revoked={self.revoked}>"
