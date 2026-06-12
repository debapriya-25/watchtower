"""Health and readiness endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.core.responses import success_response
from app.db.redis import get_redis
from app.db.session import get_db
from app.schemas.common import Envelope
from app.schemas.health import HealthData

logger = get_logger(__name__)

router = APIRouter(tags=["health"])


async def _check_postgres(db: AsyncSession) -> bool:
    try:
        await db.execute(text("SELECT 1"))
        return True
    except Exception as exc:  # noqa: BLE001 - report any failure as unhealthy
        logger.error("healthcheck_postgres_failed", error=str(exc))
        return False


async def _check_redis(redis: Redis) -> bool:
    try:
        return bool(await redis.ping())
    except Exception as exc:  # noqa: BLE001
        logger.error("healthcheck_redis_failed", error=str(exc))
        return False


@router.get(
    "/health",
    response_model=Envelope[HealthData],
    summary="Liveness & readiness probe",
    description=(
        "Reports overall service health along with PostgreSQL and Redis "
        "connectivity. Returns **200** when all components are reachable and "
        "**503** otherwise."
    ),
)
async def health_check(
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> JSONResponse:
    postgres_ok = await _check_postgres(db)
    redis_ok = await _check_redis(redis)
    healthy = postgres_ok and redis_ok

    data = HealthData(
        status="healthy" if healthy else "unhealthy",
        version=settings.app_version,
        environment=settings.app_env,
        components={
            "postgres": "ok" if postgres_ok else "error",
            "redis": "ok" if redis_ok else "error",
        },
    )

    return success_response(
        data=data.model_dump(),
        status_code=(
            status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE
        ),
    )
