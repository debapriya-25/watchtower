# Watchtower

A secure, scalable crypto **watchlist & price-alert API** (FastAPI · PostgreSQL ·
Redis). This repository contains the backend (`backend/`) and a containerized
local stack (Docker Compose).

The fastest way to run the whole thing is Docker Compose (below). To run the API
directly in a Python venv instead, see [`backend/README.md`](backend/README.md).

### Documentation map

| Doc | What's in it |
|---|---|
| [`backend/README.md`](backend/README.md) | API/feature reference, endpoints, local venv run, tests |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | System/architecture diagrams (Mermaid), data model, request lifecycle |
| [`SCALABILITY.md`](SCALABILITY.md) | Scaling strategy: stateless API, Redis cache, indexing, next steps |
| [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) | Env vars, local Docker, and cloud deploy (Render/Neon/Upstash) |
| [`docs/watchtower.postman_collection.json`](docs/watchtower.postman_collection.json) | Importable Postman collection (see *API testing* below) |
| [`docs/PRD.md`](docs/PRD.md) · [`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md) · [`docs/TECH_STACK.md`](docs/TECH_STACK.md) | Product & planning docs |

### API testing (Swagger / Postman)

- **Swagger UI** — always live at `/docs` (e.g. http://localhost:8000/docs);
  click **Authorize**, enter your email as `username` + password.
- **Postman** — either:
  1. Import [`docs/watchtower.postman_collection.json`](docs/watchtower.postman_collection.json),
     then set the collection variables `baseUrl` and `accessToken` (get a token
     from `POST /auth/login` → `data.tokens.access_token`); or
  2. Import the live spec directly: *Import → Link →* `http://localhost:8000/openapi.json`.

---

## Run with Docker (recommended)

### Prerequisites

- **Docker Engine 24+** and the **Docker Compose v2** plugin
  (`docker compose version`). Docker Desktop on Windows/macOS includes both.
- Ports: the API is published on **`BACKEND_PORT`** (default `8000`). Postgres
  and Redis are **not** published to the host (the backend reaches them over the
  private compose network), so they won't clash with anything already running
  on your machine.

### One-time setup

From the repository root, create your `.env` from the template and review it
(at minimum set a real `JWT_SECRET` and the Postgres credentials):

```bash
cp .env.example .env            # macOS / Linux
Copy-Item .env.example .env     # Windows PowerShell
```

`docker-compose.yml` reads this `.env` for the Postgres credentials and the
application config. `DATABASE_URL` / `REDIS_URL` are built automatically by
compose from those credentials and the service names — you don't set them.

### Build & start

```bash
docker compose build           # build the backend image
docker compose up -d           # start postgres, redis, backend (detached)
```

On start the backend container automatically: **waits** for Postgres and Redis,
runs **`alembic upgrade head`**, then starts the API. Compose also gates the
backend on the datastores' health checks, so ordering is correct on a cold boot.

Check status and follow logs:

```bash
docker compose ps              # service status + health
docker compose logs -f backend # follow the API logs
```

Once `backend` is `healthy`:

- API:      http://localhost:8000  (or your `BACKEND_PORT`)
- Swagger:  http://localhost:8000/docs
- Health:   http://localhost:8000/health

### Seed the catalogue (optional, one-off)

Creates the admin + demo users and pulls the top-100 CoinGecko tokens. Idempotent.

```bash
docker compose run --rm backend python -m scripts.seed
```

Default seeded logins (override via `.env`): `admin@watchtower.dev` /
`ChangeMeAdmin123!` and `demo@watchtower.dev` / `ChangeMeDemo123!`.

### Stop & remove

```bash
docker compose stop            # stop containers, keep them
docker compose down            # stop & remove containers + network (KEEPS data volumes)
docker compose down -v         # also remove the postgres/redis volumes (DELETES all data)
```

### Common Docker commands

```bash
docker compose build --no-cache backend     # clean rebuild
docker compose up -d --build                 # rebuild + (re)start
docker compose restart backend               # restart just the API
docker compose exec backend sh               # shell into the running API container
docker compose run --rm backend alembic downgrade -1   # one-off migration command
docker compose logs --tail=100 postgres      # recent postgres logs
```

---

## Local development workflow

The image bundles application code at build time (it does not bind-mount your
source), so it's optimized for a reproducible run rather than live reload.
Typical loops:

- **Iterating on the stack / dependencies:** edit code, then
  `docker compose up -d --build backend` to rebuild and restart the API.
- **Fast inner loop on code only:** run the API in a local venv against the
  Dockerized datastores — start just the datastores with
  `docker compose up -d postgres redis`, expose them if needed, and run the app
  per [`backend/README.md`](backend/README.md). (By default the datastores are
  network-internal; add a `ports:` mapping in `docker-compose.yml` to reach them
  from the host.)
- **Migrations:** they run automatically on container start. To create a new
  revision after model changes, use a one-off:
  `docker compose run --rm backend alembic revision --autogenerate -m "msg"`
  (the file is written inside the container — for authoring, prefer the local
  venv workflow).
- **Tests:** run in the local venv (see [`backend/README.md`](backend/README.md)).

---

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `bind: address already in use` on start | Host port `8000` is taken. Set `BACKEND_PORT=8010` (or any free port) in `.env` and `docker compose up -d`. |
| `backend` stuck `health: starting`, logs show `[wait] postgres not ready` | First boot is initializing Postgres; the entrypoint retries for ~2 min. Check `docker compose logs postgres`. |
| `JWT_SECRET ... Field required` / validation error on boot | `.env` is missing or incomplete. Recreate it from `.env.example` and ensure required keys are set. |
| Changes to code aren't reflected | The image copies source at build time — rebuild: `docker compose up -d --build backend`. |
| `permission denied: docker-entrypoint.sh` | The image normalizes line endings and sets `+x` at build; rebuild with `docker compose build --no-cache backend` if you edited it on Windows. |
| Catalogue empty / `GET /api/v1/tokens` returns 0 | Run the seed: `docker compose run --rm backend python -m scripts.seed`. |
| Need a clean slate | `docker compose down -v` removes the data volumes, then `up -d` re-migrates from scratch. |
| Inspect data directly | `docker compose exec postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"` |

---

## What's in the box

| Service | Image | Purpose | Volume |
|---|---|---|---|
| `postgres` | `postgres:16-alpine` | Primary database | `pgdata` |
| `redis` | `redis:7-alpine` | Price cache + rate-limit store | `redisdata` |
| `backend` | built from `Dockerfile` | FastAPI app (non-root, healthchecked) | — |

The backend image is a multi-stage build (Python 3.12-slim): dependencies are
installed into a virtualenv in a builder stage and copied into a slim runtime
that runs as a non-root `app` user, with a `HEALTHCHECK` hitting `/health`.
