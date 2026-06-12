#!/usr/bin/env sh
#
# Container entrypoint for the Watchtower backend.
#
# On every start it:
#   1. waits for PostgreSQL and Redis to accept connections,
#   2. applies database migrations (alembic upgrade head),
#   3. execs the API server (replacing the shell so signals reach uvicorn).
#
set -eu

# Datastores are needed by every entry path (API, migrations, seeding), so
# always wait for them first.
echo "[entrypoint] waiting for datastores to become available..."
python -m scripts.wait_for_services

# If a command was supplied (e.g. `docker compose run backend python -m
# scripts.seed`), run it instead of the API and exit.
if [ "$#" -gt 0 ]; then
    echo "[entrypoint] running custom command: $*"
    exec "$@"
fi

# Default path: migrate, then start the API.
echo "[entrypoint] applying database migrations..."
alembic upgrade head

echo "[entrypoint] starting API on 0.0.0.0:${PORT:-8000}..."
# --loop asyncio uses a SelectorEventLoop, which the async psycopg driver
# requires. exec replaces the shell so SIGTERM/SIGINT reach uvicorn directly.
exec python -m uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}" \
    --loop asyncio \
    --no-access-log
