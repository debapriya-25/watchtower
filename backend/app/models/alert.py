"""Alert ORM model.

Alert evaluation/notification is a later phase; only the table definition lives
here so the initial migration provisions the schema.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import AlertCondition, AlertStatus

if TYPE_CHECKING:
    from app.models.user import User


class Alert(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A user-defined price threshold for a token."""

    __tablename__ = "alerts"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    coin_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    condition: Mapped[AlertCondition] = mapped_column(
        Enum(AlertCondition, name="alert_condition", native_enum=False, length=16),
        nullable=False,
    )
    target_price: Mapped[Decimal] = mapped_column(
        Numeric(precision=24, scale=8), nullable=False
    )
    status: Mapped[AlertStatus] = mapped_column(
        Enum(AlertStatus, name="alert_status", native_enum=False, length=16),
        default=AlertStatus.ACTIVE,
        nullable=False,
    )
    triggered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user: Mapped["User"] = relationship(back_populates="alerts")

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return (
            f"<Alert coin_id={self.coin_id!r} {self.condition.value} "
            f"{self.target_price} status={self.status.value}>"
        )
