"""ORM model package.

Importing this package imports every model so that they are registered on
``Base.metadata``. Alembic imports it to discover the full schema for
autogeneration.
"""

from __future__ import annotations

from app.db.base import Base
from app.models.alert import Alert
from app.models.enums import AlertCondition, AlertStatus, UserRole
from app.models.token import Token
from app.models.user import User
from app.models.watchlist import Watchlist
from app.models.watchlist_item import WatchlistItem

__all__ = [
    "Base",
    "User",
    "Token",
    "Watchlist",
    "WatchlistItem",
    "Alert",
    "UserRole",
    "AlertCondition",
    "AlertStatus",
]
