"""Admin request/response schemas (Pydantic v2)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.schemas.token import PageMeta
from app.schemas.user import UserPublic


class AdminUserUpdate(BaseModel):
    """Payload for ``PATCH /api/v1/admin/users/{id}`` — activate/deactivate."""

    model_config = ConfigDict(json_schema_extra={"example": {"is_active": False}})

    is_active: bool


class UserList(BaseModel):
    """A page of users (admin view)."""

    items: list[UserPublic]
    pagination: PageMeta
