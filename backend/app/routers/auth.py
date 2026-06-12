"""Authentication routes: register, login, refresh, me.

Rate limiting (slowapi) is applied to ``/register`` and ``/login``. The slowapi
decorator requires the endpoint to declare a ``request: Request`` parameter.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limit import limiter
from app.core.responses import success_response
from app.db.session import get_db
from app.deps.auth import CurrentUser
from app.schemas.auth import (
    AuthResult,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
)
from app.schemas.common import Envelope, ErrorEnvelope
from app.schemas.user import UserPublic
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])

DbSession = Annotated[AsyncSession, Depends(get_db)]

_ERROR_RESPONSES = {
    400: {"model": ErrorEnvelope, "description": "Validation or request error"},
    401: {"model": ErrorEnvelope, "description": "Authentication failed"},
    409: {"model": ErrorEnvelope, "description": "Email already registered"},
    429: {"model": ErrorEnvelope, "description": "Rate limit exceeded"},
}


@router.post(
    "/register",
    response_model=Envelope[AuthResult],
    status_code=status.HTTP_201_CREATED,
    summary="Register a new account",
    responses=_ERROR_RESPONSES,
)
@limiter.limit("5/minute")
async def register(
    request: Request,
    payload: RegisterRequest,
    db: DbSession,
) -> JSONResponse:
    user, tokens = await auth_service.register_user(
        db,
        email=payload.email,
        password=payload.password,
        full_name=payload.full_name,
    )
    result = AuthResult(user=UserPublic.model_validate(user), tokens=tokens)
    return success_response(
        data=result.model_dump(), status_code=status.HTTP_201_CREATED
    )


@router.post(
    "/login",
    response_model=Envelope[AuthResult],
    summary="Authenticate and obtain tokens",
    responses=_ERROR_RESPONSES,
)
@limiter.limit("10/minute")
async def login(
    request: Request,
    payload: LoginRequest,
    db: DbSession,
) -> JSONResponse:
    user, tokens = await auth_service.authenticate_user(
        db, email=payload.email, password=payload.password
    )
    result = AuthResult(user=UserPublic.model_validate(user), tokens=tokens)
    return success_response(data=result.model_dump())


@router.post(
    "/token",
    response_model=TokenPair,
    summary="OAuth2 password token endpoint (used by Swagger 'Authorize')",
    description=(
        "Standard OAuth2 password-flow token endpoint. Accepts a form body "
        "(`username` = email, `password`) and returns a top-level "
        "`access_token`/`token_type` so the Swagger **Authorize** button works. "
        "Application clients should use `POST /auth/login` instead, which "
        "returns the standard `{success, data, error}` envelope. This endpoint "
        "intentionally returns the raw OAuth2 token shape (not the envelope) "
        "because that is what the OAuth2 spec and Swagger UI require."
    ),
    responses={401: _ERROR_RESPONSES[401], 429: _ERROR_RESPONSES[429]},
)
@limiter.limit("10/minute")
async def token(
    request: Request,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: DbSession,
) -> JSONResponse:
    # ``username`` carries the email for the OAuth2 password flow.
    _user, tokens = await auth_service.authenticate_user(
        db, email=form_data.username, password=form_data.password
    )
    # Return the raw OAuth2 token shape (top-level ``access_token``) so the
    # Swagger Authorize popup can read it. A JSONResponse (not a bare model) is
    # required because the slowapi rate limiter injects headers into a Response.
    return JSONResponse(content=jsonable_encoder(tokens.model_dump()))


@router.post(
    "/refresh",
    response_model=Envelope[TokenPair],
    summary="Rotate a refresh token for a new token pair",
    responses=_ERROR_RESPONSES,
)
async def refresh(
    payload: RefreshRequest,
    db: DbSession,
) -> JSONResponse:
    tokens = await auth_service.refresh_tokens(
        db, refresh_token=payload.refresh_token
    )
    return success_response(data=tokens.model_dump())


@router.get(
    "/me",
    response_model=Envelope[UserPublic],
    summary="Get the currently authenticated user",
    responses={401: _ERROR_RESPONSES[401]},
)
async def me(current_user: CurrentUser) -> JSONResponse:
    return success_response(
        data=UserPublic.model_validate(current_user).model_dump()
    )
