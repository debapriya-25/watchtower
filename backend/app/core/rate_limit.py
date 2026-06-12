"""Rate limiting via slowapi, backed by Redis for cross-worker correctness.

The shared :data:`limiter` is attached to the FastAPI app in ``main.py`` and
applied to individual routes with the ``@limiter.limit(...)`` decorator.
"""

from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings

# Using the configured Redis instance as the storage backend means limits are
# enforced consistently across multiple uvicorn workers/processes.
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=settings.redis_url,
    strategy="fixed-window",
    headers_enabled=True,
)
