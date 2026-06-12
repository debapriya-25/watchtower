"""Authentication request/response schemas."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.schemas.user import UserPublic


class RegisterRequest(BaseModel):
    """Payload for ``POST /auth/register``."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "alice@example.com",
                "password": "S3curePass!",
                "full_name": "Alice Example",
            }
        }
    )

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)


class LoginRequest(BaseModel):
    """Payload for ``POST /auth/login``."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"email": "alice@example.com", "password": "S3curePass!"}
        }
    )

    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class RefreshRequest(BaseModel):
    """Payload for ``POST /auth/refresh``."""

    refresh_token: str = Field(min_length=1)


class TokenPair(BaseModel):
    """Issued access + refresh token pair."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Access-token lifetime in seconds.")


class AuthResult(BaseModel):
    """Returned by register/login: the user plus a fresh token pair."""

    user: UserPublic
    tokens: TokenPair
