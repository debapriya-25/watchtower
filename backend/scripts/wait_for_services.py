"""Block until PostgreSQL and Redis are reachable.

Run by the container entrypoint before migrations so the API never starts
against a datastore that is still booting. Reads ``DATABASE_URL`` and
``REDIS_URL`` from the environment (no app imports — keeps it dependency-light
and fast).

Usage:  python -m scripts.wait_for_services
"""

from __future__ import annotations

import os
import sys
import time

import psycopg
import redis


def _wait_postgres(url: str, *, retries: int = 60, delay: float = 2.0) -> None:
    # SQLAlchemy uses the ``postgresql+psycopg`` driver prefix; libpq wants a
    # plain ``postgresql`` URL.
    conninfo = url.replace("postgresql+psycopg://", "postgresql://", 1)
    for attempt in range(1, retries + 1):
        try:
            with psycopg.connect(conninfo, connect_timeout=3) as conn:
                conn.execute("SELECT 1")
            print("[wait] postgres is ready", flush=True)
            return
        except Exception as exc:  # noqa: BLE001 - any failure means "not ready"
            print(
                f"[wait] postgres not ready ({attempt}/{retries}): "
                f"{exc.__class__.__name__}",
                flush=True,
            )
            time.sleep(delay)
    print("[wait] postgres did not become ready in time", file=sys.stderr)
    sys.exit(1)


def _wait_redis(url: str, *, retries: int = 60, delay: float = 2.0) -> None:
    for attempt in range(1, retries + 1):
        try:
            client = redis.from_url(url, socket_connect_timeout=3)
            client.ping()
            client.close()
            print("[wait] redis is ready", flush=True)
            return
        except Exception as exc:  # noqa: BLE001
            print(
                f"[wait] redis not ready ({attempt}/{retries}): "
                f"{exc.__class__.__name__}",
                flush=True,
            )
            time.sleep(delay)
    print("[wait] redis did not become ready in time", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    database_url = os.environ.get("DATABASE_URL")
    redis_url = os.environ.get("REDIS_URL")
    if not database_url or not redis_url:
        print(
            "[wait] DATABASE_URL and REDIS_URL must be set", file=sys.stderr
        )
        sys.exit(1)

    _wait_postgres(database_url)
    _wait_redis(redis_url)
    print("[wait] all datastores ready", flush=True)


if __name__ == "__main__":
    main()
