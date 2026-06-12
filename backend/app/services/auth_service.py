"""Authentication service layer.

Contains all auth business logic (user creation, credential verification, token
issuance, refresh-token rotation) so the routers stay thin. Functions accept an
``AsyncSession`` and operate using SQLAlchemy 2.0 style queries.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AuthenticationError, ConflictError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.schemas.auth import TokenPair


# --------------------------------------------------------------------------- #
# Queries
# --------------------------------------------------------------------------- #
async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    return await db.get(User, user_id)


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(
        select(User).where(User.email == email.lower())
    )
    return result.scalar_one_or_none()


# --------------------------------------------------------------------------- #
# Token issuance
# --------------------------------------------------------------------------- #
async def _issue_token_pair(db: AsyncSession, user: User) -> TokenPair:
    """Create an access/refresh pair and persist the refresh token's ``jti``."""
    access_token, _, _ = create_access_token(subject=str(user.id))
    refresh_token, refresh_jti, refresh_exp = create_refresh_token(
        subject=str(user.id)
    )

    db.add(
        RefreshToken(user_id=user.id, jti=refresh_jti, expires_at=refresh_exp)
    )
    await db.flush()

    return TokenPair(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.access_token_ttl_min * 60,
    )


# --------------------------------------------------------------------------- #
# Use cases
# --------------------------------------------------------------------------- #
async def register_user(
    db: AsyncSession,
    *,
    email: str,
    password: str,
    full_name: str | None,
) -> tuple[User, TokenPair]:
    """Create a new user and issue an initial token pair."""
    normalized_email = email.lower()
    if await get_user_by_email(db, normalized_email) is not None:
        raise ConflictError("An account with this email already exists.")

    user = User(
        email=normalized_email,
        hashed_password=hash_password(password),
        full_name=full_name,
    )
    db.add(user)
    await db.flush()  # populate user.id / timestamps

    tokens = await _issue_token_pair(db, user)
    await db.refresh(user)
    return user, tokens


async def authenticate_user(
    db: AsyncSession, *, email: str, password: str
) -> tuple[User, TokenPair]:
    """Verify credentials and issue a token pair."""
    user = await get_user_by_email(db, email)
    # Verify against the stored hash (or a dummy) to keep timing uniform and
    # avoid leaking which emails exist.
    placeholder = "$argon2id$v=19$m=65536,t=3,p=4$" + "A" * 22
    valid = verify_password(password, user.hashed_password if user else placeholder)

    if user is None or not valid:
        raise AuthenticationError("Invalid email or password.")
    if not user.is_active:
        raise AuthenticationError("User account is disabled.")

    tokens = await _issue_token_pair(db, user)
    return user, tokens


async def refresh_tokens(db: AsyncSession, *, refresh_token: str) -> TokenPair:
    """Validate a refresh token, rotate it, and return a new token pair.

    Implements refresh-token rotation: the presented token's ``jti`` is revoked
    and a brand-new refresh token is issued.
    """
    from app.core.security import JWTError, decode_token  # local import

    try:
        payload = decode_token(refresh_token)
    except JWTError as exc:
        raise AuthenticationError("Invalid or expired refresh token.") from exc

    if payload.get("type") != "refresh":
        raise AuthenticationError("Invalid token type.")

    jti = payload.get("jti")
    subject = payload.get("sub")
    if not jti or not subject:
        raise AuthenticationError("Invalid refresh token payload.")

    result = await db.execute(
        select(RefreshToken).where(RefreshToken.jti == jti)
    )
    stored = result.scalar_one_or_none()
    if stored is None or stored.revoked:
        raise AuthenticationError("Refresh token has been revoked.")
    if stored.expires_at <= datetime.now(timezone.utc):
        raise AuthenticationError("Refresh token has expired.")

    user = await get_user_by_id(db, uuid.UUID(subject))
    if user is None or not user.is_active:
        raise AuthenticationError("User no longer exists or is disabled.")

    # Rotate: revoke the old token, issue a fresh pair.
    stored.revoked = True
    await db.flush()
    return await _issue_token_pair(db, user)
