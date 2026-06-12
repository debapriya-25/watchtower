"""Helpers for the standard API response envelope.

Every endpoint returns the shape::

    {"success": true|false, "data": {...}|null, "error": null|{...}}

Use :func:`success_response` / :func:`error_response` to build the payloads and
:class:`Envelope` (in ``app.schemas.common``) for OpenAPI documentation.
"""

from __future__ import annotations

from typing import Any

from fastapi import status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse


def success_payload(data: Any = None) -> dict[str, Any]:
    """Build a success envelope dictionary."""
    return {"success": True, "data": data, "error": None}


def error_payload(
    message: str,
    code: str,
    details: Any = None,
) -> dict[str, Any]:
    """Build an error envelope dictionary."""
    error: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return {"success": False, "data": None, "error": error}


def success_response(
    data: Any = None,
    status_code: int = status.HTTP_200_OK,
) -> JSONResponse:
    """Return a :class:`JSONResponse` wrapping ``data`` in a success envelope."""
    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder(success_payload(data)),
    )


def error_response(
    message: str,
    code: str,
    status_code: int = status.HTTP_400_BAD_REQUEST,
    details: Any = None,
) -> JSONResponse:
    """Return a :class:`JSONResponse` wrapping an error envelope."""
    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder(error_payload(message, code, details)),
    )
