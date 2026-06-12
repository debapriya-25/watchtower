"""Admin service: user management (list, activate/deactivate).

Admin authorization is enforced at the router layer via the ``require_admin``
dependency; these functions assume the caller is already an administrator.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.models.user import User

logger = get_logger(__name__)


async def list_users(
    db: AsyncSession, *, page: int, size: int
) -> tuple[list[User], int]:
    """Return a page of users (newest first) plus the total user count."""
    offset = (page - 1) * size

    total = await db.scalar(select(func.count()).select_from(User))
    result = await db.execute(
        select(User).order_by(User.created_at.desc()).offset(offset).limit(size)
    )
    return list(result.scalars().all()), int(total or 0)


async def set_user_active(
    db: AsyncSession, user_id: uuid.UUID, *, is_active: bool
) -> User:
    """Activate or deactivate a user; raise :class:`NotFoundError` if missing."""
    user = await db.get(User, user_id)
    if user is None:
        raise NotFoundError("User not found.")

    user.is_active = is_active
    await db.flush()
    await db.refresh(user)
    logger.info(
        "admin_user_active_set", user_id=str(user_id), is_active=is_active
    )
    return user
