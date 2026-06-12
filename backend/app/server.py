"""Programmatic server entrypoint and event-loop factory.

psycopg's async mode is incompatible with the ``ProactorEventLoop`` that uvicorn
selects by default on Windows. :func:`loop_factory` forces a
``SelectorEventLoop`` there (and uses the standard loop elsewhere) so the async
PostgreSQL driver works on every platform.

Run the server with either:

    python -m app.server
    # or, using the uvicorn CLI with the custom loop:
    uvicorn app.main:app --loop app.server:loop_factory
"""

from __future__ import annotations

import asyncio
import sys

import uvicorn


def loop_factory() -> asyncio.AbstractEventLoop:
    """Return an event loop compatible with psycopg's async mode."""
    if sys.platform == "win32":
        return asyncio.SelectorEventLoop()
    return asyncio.new_event_loop()


def run() -> None:
    """Start the development server."""
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        loop="app.server:loop_factory",
    )


if __name__ == "__main__":
    run()
