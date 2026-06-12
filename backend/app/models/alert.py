"""Alert ORM model.

A user-defined price threshold on a catalogue token. When the token's price
crosses the threshold the alert "triggers": ``triggered_at`` is stamped and
``is_active`` is set to ``False`` (one-shot). Evaluation logic lives in
``app.services.alert_service`` — there is no scheduler/worker in this phase.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import AlertCondition

if TYPE_CHECKING:
    from app.models.token import Token
    from app.models.user import User


class Alert(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A user-defined price threshold for a catalogue token."""

    __tablename__ = "alerts"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    token_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tokens.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    condition: Mapped[AlertCondition] = mapped_column(
        Enum(AlertCondition, name="alert_condition", native_enum=False, length=16),
        nullable=False,
    )
    target_price: Mapped[Decimal] = mapped_column(
        Numeric(precision=24, scale=8), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, index=True
    )
    triggered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user: Mapped["User"] = relationship(back_populates="alerts")
    token: Mapped["Token"] = relationship(lazy="raise")

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return (
            f"<Alert token_id={self.token_id!s} {self.condition.value} "
            f"{self.target_price} is_active={self.is_active}>"
        )
