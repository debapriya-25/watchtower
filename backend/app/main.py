"""Watchtower API application bootstrap.

Wires together configuration, logging, datastore lifecycle, rate limiting,
global exception handling and routers into a single FastAPI application.
"""

from __future__ import annotations

import asyncio
import sys

# psycopg's async mode cannot run on the Windows default ProactorEventLoop;
# install a SelectorEventLoop policy before any event loop is created.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.middleware import SlowAPIMiddleware

from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.core.rate_limit import limiter
from app.db.redis import close_redis
from app.db.session import dispose_engine
from app.routers import auth, health, tokens

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage start-up and shutdown of shared resources."""
    logger.info(
        "application_startup",
        app=settings.app_name,
        version=settings.app_version,
        environment=settings.app_env,
    )
    try:
        yield
    finally:
        await dispose_engine()
        await close_redis()
        logger.info("application_shutdown")


tags_metadata = [
    {"name": "health", "description": "Liveness and readiness probes."},
    {
        "name": "auth",
        "description": "Registration, login, token refresh and current-user lookup.",
    },
    {
        "name": "tokens",
        "description": (
            "Crypto token catalogue and live, Redis-cached prices. Listing is "
            "open to any authenticated user; creating/updating catalogue entries "
            "is admin-only."
        ),
    },
]

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Watchtower — a crypto watchlist & price-alert API. "
        "All responses use the envelope `{success, data, error}`."
    ),
    openapi_tags=tags_metadata,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# --- Rate limiting ------------------------------------------------------- #
# Expose the limiter on app state and install the middleware. The
# RateLimitExceeded handler is registered in register_exception_handlers.
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)

# --- CORS ---------------------------------------------------------------- #
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Exception handlers -------------------------------------------------- #
register_exception_handlers(app)

# --- Routers ------------------------------------------------------------- #
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(tokens.router)


@app.get("/", tags=["health"], summary="Service banner")
async def root() -> dict[str, object]:
    """Minimal root endpoint returning the standard envelope."""
    return {
        "success": True,
        "data": {
            "service": settings.app_name,
            "version": settings.app_version,
            "docs": "/docs",
        },
        "error": None,
    }
