# Watchtower — Deployment

How to run the stack locally with Docker and how to deploy the backend to a
free-tier cloud (Render + Neon + Upstash). The image is production-shaped
(multi-stage, non-root, healthchecked, migrations on start).

---

## 1. Local (Docker Compose)

Brings up `postgres`, `redis`, and `backend` with one command. Full command
reference is in the root [`README.md`](../README.md).

```bash
cp .env.example .env          # set JWT_SECRET + Postgres creds
docker compose build
docker compose up -d
docker compose run --rm backend python -m scripts.seed   # optional seed
```

- API:     http://localhost:8000  (override with `BACKEND_PORT`)
- Swagger:  http://localhost:8000/docs
- Health:   http://localhost:8000/health

On start the backend **waits for Postgres + Redis → runs `alembic upgrade head`
→ starts Uvicorn** (see `backend/docker-entrypoint.sh`).

---

## 2. Environment variables

Compose builds `DATABASE_URL` / `REDIS_URL` from the Postgres credentials + the
service names, so locally you only set the values in `.env`. In a cloud
deployment you set `DATABASE_URL` and `REDIS_URL` directly to the managed
provider URLs.

| Variable | Required | Default | Notes |
|---|---|---|---|
| `APP_ENV` | no | `development` | `production` enables JSON logs |
| `DATABASE_URL` | **yes** | — | `postgresql+psycopg://user:pass@host:5432/db` (async psycopg driver) |
| `REDIS_URL` | **yes** | — | `redis://host:6379/0` (use `rediss://` for TLS, e.g. Upstash) |
| `JWT_SECRET` | **yes** | — | **set a strong random value in production** |
| `JWT_ALGORITHM` | no | `HS256` | |
| `ACCESS_TOKEN_TTL_MIN` | no | `15` | access-token lifetime |
| `REFRESH_TOKEN_TTL_DAYS` | no | `7` | refresh-token lifetime |
| `PRICE_CACHE_TTL_SEC` | no | `30` | price cache TTL |
| `COINGECKO_BASE` | no | `https://api.coingecko.com/api/v3` | |
| `COINGECKO_API_KEY` | no | — | optional demo/pro key (`x-cg-demo-api-key`) |
| `COINGECKO_TIMEOUT_SEC` | no | `10` | per-request timeout |
| `COINGECKO_MAX_RETRIES` | no | `3` | transient-failure retries |
| `PRICE_VS_CURRENCY` | no | `usd` | |
| `TOP_TOKENS_COUNT` | no | `100` | seed catalogue size |
| `CORS_ORIGINS` | no | `http://localhost:5173` | comma-separated; **lock to the frontend origin in prod** |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | no | `admin@watchtower.dev` / `ChangeMe…` | seeded admin — **change before real use** |
| `DEMO_EMAIL` / `DEMO_PASSWORD` | no | `demo@watchtower.dev` / `ChangeMe…` | seeded demo user |
| `BACKEND_PORT` | no | `8000` | host port published by compose (local only) |

Compose-only (PostgreSQL service): `POSTGRES_USER`, `POSTGRES_PASSWORD`,
`POSTGRES_DB`.

---

## 3. Cloud deployment (free tier)

Reference targets from the Tech Stack doc. The backend is provider-agnostic —
anything that runs a Docker image + gives you managed Postgres and Redis works.

### 3.1 PostgreSQL — Neon
1. Create a Neon project → copy the connection string.
2. Convert it to the async psycopg form for `DATABASE_URL`:
   `postgresql+psycopg://USER:PASSWORD@HOST/DB?sslmode=require`

### 3.2 Redis — Upstash
1. Create an Upstash Redis database → copy the `rediss://` URL into `REDIS_URL`
   (TLS).

### 3.3 API — Render (Docker)
1. New **Web Service** → "Deploy from a Git repo" → Docker.
2. Dockerfile path: `./Dockerfile`, context: repo root (already correct).
3. Set environment variables (section 2): `DATABASE_URL`, `REDIS_URL`,
   `JWT_SECRET` (strong), `APP_ENV=production`, `CORS_ORIGINS=<frontend origin>`,
   and any CoinGecko/seed overrides.
4. The container entrypoint runs `alembic upgrade head` automatically on each
   deploy, so the schema is migrated before the API serves traffic.
5. Health check path: `/health` (returns 200 when DB + Redis are reachable).

### 3.4 Seed once (after first deploy)
Run the seed as a one-off against the deployed datastores:

- Render: open a **Shell** on the service and run `python -m scripts.seed`, or
  run a one-off job with the same image and command.
- Locally against cloud datastores: set `DATABASE_URL`/`REDIS_URL` to the cloud
  URLs and run `python -m scripts.seed` from `backend/`.

The seed is **idempotent** (safe to re-run): it creates the admin + demo users
and the top-`TOP_TOKENS_COUNT` CoinGecko tokens, skipping any that already exist.

---

## 4. Production checklist

- [ ] Strong, unique `JWT_SECRET` (not the example value).
- [ ] `APP_ENV=production` (structured JSON logs).
- [ ] `CORS_ORIGINS` restricted to the real frontend origin(s).
- [ ] Managed Postgres with TLS (`sslmode=require`) and Redis over `rediss://`.
- [ ] Changed `ADMIN_PASSWORD` / `DEMO_PASSWORD` (or remove the demo user).
- [ ] Migrations applied (automatic via entrypoint) — verify `/health` is 200.
- [ ] Seed run once; admin can log in and `GET /api/v1/admin/users`.
- [ ] (Scale) run multiple replicas and/or Gunicorn workers — the API is
      stateless (see [`../SCALABILITY.md`](../SCALABILITY.md)).

---

## 5. Migrations

```bash
# inside the container (automatic on start) or locally from backend/
alembic upgrade head                 # apply
alembic current                      # show current revision
alembic downgrade -1                 # roll back one
alembic revision --autogenerate -m "msg"   # author a new revision (review before commit)
```

---

## 6. API testing (Postman / Swagger)

- **Swagger UI** is always live at `/docs` and reflects the deployed build.
- **Postman:** import the bundled collection
  [`watchtower.postman_collection.json`](watchtower.postman_collection.json)
  (set the `baseUrl` and `accessToken` collection variables), **or** import the
  live spec directly in Postman via *Import → Link →*
  `https://<host>/openapi.json`. See the README "API testing" section.
