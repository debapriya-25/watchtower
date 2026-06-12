"""Authentication & authorization dependencies (RBAC).

Provides:
  * :func:`get_current_user` – resolves the bearer access token to a ``User``.
  * :func:`require_admin` – ensures the current user has the admin role.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationError, PermissionDeniedError
from app.core.security import JWTError, decode_token
from app.db.session import get_db
from app.models.user import User
from app.services import auth_service

# ``tokenUrl`` powers the Swagger "Authorize" button. It points at the dedicated
# OAuth2 token endpoint (``POST /auth/token``) which speaks the standard OAuth2
# password flow (form body + top-level ``access_token``) that Swagger UI expects.
# ``/auth/login`` keeps its JSON + ``{success,data,error}`` envelope contract for
# the application/frontend. ``auto_error`` is disabled so we can raise our own
# enveloped 401 instead of FastAPI's default.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token", auto_error=False)

DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    db: DbSession,
    token: Annotated[str | None, Depends(oauth2_scheme)],
) -> User:
    """Resolve and return the authenticated :class:`User`.

    Raises :class:`AuthenticationError` if the token is missing, malformed,
    expired, of the wrong type, or refers to an inactive/unknown user.
    """
    if not token:
        raise AuthenticationError("Not authenticated.")

    try:
        payload = decode_token(token)
    except JWTError as exc:
        raise AuthenticationError("Invalid or expired token.") from exc

    if payload.get("type") != "access":
        raise AuthenticationError("Invalid token type.")

    subject = payload.get("sub")
    if not subject:
        raise AuthenticationError("Invalid token payload.")

    try:
        user_id = uuid.UUID(subject)
    except (ValueError, TypeError) as exc:
        raise AuthenticationError("Invalid token subject.") from exc

    user = await auth_service.get_user_by_id(db, user_id)
    if user is None:
        raise AuthenticationError("User no longer exists.")
    if not user.is_active:
        raise AuthenticationError("User account is disabled.")

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def require_admin(current_user: CurrentUser) -> User:
    """Ensure the current user is an administrator."""
    if not current_user.is_admin:
        raise PermissionDeniedError("Administrator privileges required.")
    return current_user


AdminUser = Annotated[User, Depends(require_admin)]
