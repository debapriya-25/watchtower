"""Async Redis connection management.

A single connection pool is shared for the lifetime of the process. Use
:func:`get_redis` as a FastAPI dependency, and call :func:`close_redis` on
application shutdown.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

import redis.asyncio as aioredis
from redis.asyncio import Redis

from app.core.config import settings

# A single client backed by a connection pool. ``decode_responses=True`` keeps
# values as ``str`` rather than ``bytes`` for ergonomic application code.
redis_client: Redis = aioredis.from_url(
    settings.redis_url,
    encoding="utf-8",
    decode_responses=True,
    health_check_interval=30,
)


async def get_redis() -> AsyncGenerator[Redis, None]:
    """FastAPI dependency yielding the shared Redis client."""
    yield redis_client


async def close_redis() -> None:
    """Close the Redis client and its connection pool (called on shutdown)."""
    await redis_client.aclose()
