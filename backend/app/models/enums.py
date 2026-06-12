"""Enumerations shared across ORM models and Pydantic schemas."""

from __future__ import annotations

import enum


class UserRole(str, enum.Enum):
    """Role used for RBAC checks."""

    USER = "user"
    ADMIN = "admin"


class AlertCondition(str, enum.Enum):
    """Trigger condition for a price alert.

    ``ABOVE`` triggers when current price >= target; ``BELOW`` when <= target.
    """

    ABOVE = "ABOVE"
    BELOW = "BELOW"
