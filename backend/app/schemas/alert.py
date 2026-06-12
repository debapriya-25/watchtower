"""Price-alert request/response schemas (Pydantic v2)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import AlertCondition
from app.schemas.token import TokenPublic


# --------------------------------------------------------------------------- #
# Requests
# --------------------------------------------------------------------------- #
class AlertCreate(BaseModel):
    """Payload for ``POST /api/v1/alerts``."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "token_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                "condition": "ABOVE",
                "target_price": 75000.0,
            }
        }
    )

    token_id: uuid.UUID = Field(description="Catalogue token to watch.")
    condition: AlertCondition = Field(description="ABOVE or BELOW.")
    target_price: float = Field(gt=0, description="Trigger threshold; must be > 0.")


class AlertUpdate(BaseModel):
    """Payload for ``PATCH /api/v1/alerts/{id}``.

    Only the provided fields change. Use the dedicated
    ``activate`` / ``deactivate`` endpoints to toggle ``is_active``.
    """

    model_config = ConfigDict(
        json_schema_extra={"example": {"target_price": 80000.0, "condition": "ABOVE"}}
    )

    condition: AlertCondition | None = None
    target_price: float | None = Field(default=None, gt=0)


# --------------------------------------------------------------------------- #
# Responses
# --------------------------------------------------------------------------- #
class AlertPublic(BaseModel):
    """Public representation of an alert (with embedded token details)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    token_id: uuid.UUID
    condition: AlertCondition
    target_price: float
    is_active: bool
    triggered_at: datetime | None
    created_at: datetime
    updated_at: datetime
    token: TokenPublic


class AlertList(BaseModel):
    """A user's alerts."""

    items: list[AlertPublic]
    total: int
