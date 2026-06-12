"""Async SQLAlchemy 2.0 engine and session management.

Exposes:
  * ``engine`` – the shared :class:`AsyncEngine`.
  * ``AsyncSessionLocal`` – an :func:`async_sessionmaker` factory.
  * :func:`get_db` – a FastAPI dependency yielding a request-scoped session.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

engine: AsyncEngine = create_async_engine(
    settings.async_database_url,
    echo=False,
    pool_pre_ping=True,
    future=True,
)

AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield a request-scoped :class:`AsyncSession`.

    The session is committed on successful completion of the request handler
    and rolled back if the handler raises; it is always closed afterwards.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def dispose_engine() -> None:
    """Dispose of the engine's connection pool (called on shutdown)."""
    await engine.dispose()
