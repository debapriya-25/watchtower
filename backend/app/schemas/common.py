"""Shared Pydantic schemas, including the generic response envelope.

These models exist primarily so the OpenAPI schema documents the
``{"success", "data", "error"}`` envelope used by every endpoint.
"""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

DataT = TypeVar("DataT")


class ErrorDetail(BaseModel):
    """The ``error`` member of a failure envelope."""

    code: str
    message: str
    details: object | None = None


class Envelope(BaseModel, Generic[DataT]):
    """Standard response envelope ``{success, data, error}``."""

    model_config = ConfigDict(from_attributes=True)

    success: bool = True
    data: DataT | None = None
    error: ErrorDetail | None = None


class ErrorEnvelope(BaseModel):
    """Envelope used for documented error responses."""

    success: bool = False
    data: None = None
    error: ErrorDetail


class MessageData(BaseModel):
    """Simple ``{"message": ...}`` payload."""

    message: str
