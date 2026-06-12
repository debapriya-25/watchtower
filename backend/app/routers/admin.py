"""Admin user-management routes (``/api/v1/admin``).

Every route requires an **administrator** (via the existing ``require_admin``
dependency); non-admin authenticated users receive **403**.

* ``GET   /api/v1/admin/users``        — list all users (paginated)
* ``PATCH /api/v1/admin/users/{id}``   — activate / deactivate a user
"""

from __future__ import annotations

import math
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.responses import success_response
from app.db.session import get_db
from app.deps.auth import AdminUser
from app.schemas.admin import AdminUserUpdate, UserList
from app.schemas.common import Envelope, ErrorEnvelope
from app.schemas.token import PageMeta
from app.schemas.user import UserPublic
from app.services import admin_service

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

DbSession = Annotated[AsyncSession, Depends(get_db)]

_ADMIN_RESPONSES = {
    401: {"model": ErrorEnvelope, "description": "Authentication required"},
    403: {"model": ErrorEnvelope, "description": "Administrator privileges required"},
}


@router.get(
    "/users",
    response_model=Envelope[UserList],
    summary="List all users (admin only)",
    description=(
        "Returns a paginated list of every user account, newest first. "
        "Restricted to administrators; authenticated non-admins receive 403. "
        "Each entry exposes `id`, `email`, `role`, `is_active`, `created_at` "
        "and `updated_at` (never the password hash)."
    ),
    responses=_ADMIN_RESPONSES,
)
async def list_users(
    admin: AdminUser,
    db: DbSession,
    page: Annotated[int, Query(ge=1, description="1-based page number")] = 1,
    size: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 20,
) -> JSONResponse:
    users, total = await admin_service.list_users(db, page=page, size=size)
    data = UserList(
        items=[UserPublic.model_validate(u) for u in users],
        pagination=PageMeta(
            page=page,
            size=size,
            total=total,
            pages=math.ceil(total / size) if size else 0,
        ),
    )
    return success_response(data=data.model_dump())


@router.patch(
    "/users/{user_id}",
    response_model=Envelope[UserPublic],
    summary="Activate or deactivate a user (admin only)",
    description=(
        "Sets a user's `is_active` flag. Deactivated users can no longer "
        "authenticate. Restricted to administrators (403 for non-admins); "
        "returns 404 if the user does not exist."
    ),
    responses={
        **_ADMIN_RESPONSES,
        404: {"model": ErrorEnvelope, "description": "User not found"},
    },
)
async def update_user(
    admin: AdminUser,
    db: DbSession,
    payload: AdminUserUpdate,
    user_id: Annotated[uuid.UUID, Path(description="User id")],
) -> JSONResponse:
    user = await admin_service.set_user_active(
        db, user_id, is_active=payload.is_active
    )
    return success_response(data=UserPublic.model_validate(user).model_dump())
