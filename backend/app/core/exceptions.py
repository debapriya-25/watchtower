"""Application exceptions and global exception handlers.

All handlers emit the standard response envelope so clients receive a uniform
error shape regardless of where the failure originated.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_logger
from app.core.responses import error_response

logger = get_logger(__name__)


class AppError(Exception):
    """Base class for expected, domain-level application errors.

    Raising an ``AppError`` (or subclass) produces a structured error envelope
    with the given HTTP status, machine-readable ``code`` and message.
    """

    status_code: int = status.HTTP_400_BAD_REQUEST
    code: str = "app_error"
    message: str = "An application error occurred."

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        status_code: int | None = None,
        details: Any = None,
    ) -> None:
        self.message = message or self.message
        self.code = code or self.code
        self.status_code = status_code or self.status_code
        self.details = details
        super().__init__(self.message)


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"
    message = "Resource not found."


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "conflict"
    message = "Resource already exists."


class AuthenticationError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "authentication_failed"
    message = "Authentication failed."


class PermissionDeniedError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "permission_denied"
    message = "You do not have permission to perform this action."


# --------------------------------------------------------------------------- #
# Handlers
# --------------------------------------------------------------------------- #
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    logger.warning(
        "app_error",
        path=request.url.path,
        code=exc.code,
        status_code=exc.status_code,
        message=exc.message,
    )
    return error_response(
        message=exc.message,
        code=exc.code,
        status_code=exc.status_code,
        details=exc.details,
    )


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    # ``detail`` may already be a structured payload; coerce to a string message.
    message = exc.detail if isinstance(exc.detail, str) else "HTTP error."
    return error_response(
        message=message,
        code=f"http_{exc.status_code}",
        status_code=exc.status_code,
        details=None if isinstance(exc.detail, str) else exc.detail,
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return error_response(
        message="Request validation failed.",
        code="validation_error",
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        details=exc.errors(),
    )


async def rate_limit_handler(
    request: Request, exc: RateLimitExceeded
) -> JSONResponse:
    logger.warning("rate_limit_exceeded", path=request.url.path, limit=str(exc.limit))
    return error_response(
        message=f"Rate limit exceeded: {exc.detail}.",
        code="rate_limit_exceeded",
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
    )


async def sqlalchemy_exception_handler(
    request: Request, exc: SQLAlchemyError
) -> JSONResponse:
    logger.error("database_error", path=request.url.path, error=str(exc))
    return error_response(
        message="A database error occurred.",
        code="database_error",
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


async def coingecko_exception_handler(
    request: Request, exc: "CoinGeckoError"
) -> JSONResponse:
    logger.error("upstream_price_error", path=request.url.path, error=str(exc))
    return error_response(
        message="The price provider is currently unavailable. Please retry.",
        code="upstream_unavailable",
        status_code=status.HTTP_502_BAD_GATEWAY,
    )


async def unhandled_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    logger.exception("unhandled_exception", path=request.url.path)
    return error_response(
        message="An internal server error occurred.",
        code="internal_server_error",
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Attach all global exception handlers to the FastAPI app."""
    app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RateLimitExceeded, rate_limit_handler)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(SQLAlchemyError, sqlalchemy_exception_handler)  # type: ignore[arg-type]
    # Imported here to avoid a module-load cycle (services import core.*).
    from app.services.coingecko import CoinGeckoError

    app.add_exception_handler(CoinGeckoError, coingecko_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_exception_handler)
