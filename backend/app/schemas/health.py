"""Health-check response schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

ComponentStatus = Literal["ok", "error"]


class HealthComponents(BaseModel):
    """Connectivity status of each backing service."""

    postgres: ComponentStatus
    redis: ComponentStatus


class HealthData(BaseModel):
    """Overall service health payload."""

    status: Literal["healthy", "unhealthy"]
    version: str
    environment: str
    components: HealthComponents
