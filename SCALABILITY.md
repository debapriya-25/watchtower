# Watchtower — Scalability

How the backend stays fast and correct as users, watchlists, alerts, and request
volume grow — and the concrete next steps when a single instance is no longer
enough.

## What's built today

### Stateless API → horizontal scale
The API holds **no per-user session state**. Identity travels in a signed JWT
access token, so any instance can serve any request. You can run N replicas of
the `backend` container behind a load balancer and scale out linearly; there is
nothing sticky to coordinate. Refresh tokens are the only server-side auth state
and they live in PostgreSQL (the `refresh_tokens` table), shared by all
instances, which also makes server-side revocation/rotation work across
replicas.

### Redis read-through cache on the hot, external path
Live prices are the hottest, slowest path (an outbound CoinGecko call). They are
served through a **read-through Redis cache** keyed `price:{coingecko_id}:{ccy}`
with a TTL of `PRICE_CACHE_TTL_SEC` (default 30s):

1. check Redis → on hit return immediately (`cached: true`),
2. on miss call CoinGecko, store the result, return (`cached: false`).

This collapses repeated price reads to a single upstream call per token per TTL
window, bounds staleness, and shields both CoinGecko (rate limits) and the DB.
Redis is shared across API replicas, so the cache is effective fleet-wide.

### Rate limiting backed by Redis
Auth endpoints (`/auth/register`, `/auth/login`, `/auth/token`) are throttled
per client IP with `slowapi` using **Redis as the storage backend**, so limits
are enforced consistently across all API instances rather than per-process.

### Indexes + bounded queries
- Foreign keys (`user_id`, `watchlist_id`, `token_id`, …) and `users.email`,
  `tokens.coingecko_id`, `tokens.symbol` are indexed.
- Ownership queries filter by `user_id` (indexed), so a user's data access stays
  flat as total rows grow.
- List endpoints that can grow unbounded (`/tokens`, `/admin/users`) are
  **paginated** (`page`/`size`), keeping result sets and payloads bounded.
- `UNIQUE` constraints (`(user_id, name)` watchlists, `(watchlist_id, token_id)`
  items, `tokens.coingecko_id`) enforce integrity in the DB rather than via
  read-modify-write races.

### Connection pooling
SQLAlchemy's async engine pools connections (`pool_pre_ping=True` to drop dead
connections), so bursts reuse warm connections instead of reconnecting.

## Where it goes next (named, not built)

- **Background worker (Celery/RQ + beat):** evaluate active alerts on a schedule
  against cached prices and dispatch notifications. The pure `evaluate_alert()`
  logic already exists and is side-effect-contained, so a worker can call it
  directly — no API changes required.
- **PostgreSQL read replicas:** route read-heavy traffic (token catalogue,
  list endpoints) to replicas; keep writes on the primary.
- **Cache warming / stampede control:** pre-warm popular tokens and add a short
  lock or `SETNX` guard so a cache miss under load fans out to one upstream call,
  not many.
- **API gateway + per-tenant rate tiers:** move rate limiting to the edge and
  offer differentiated tiers.
- **Gunicorn + multiple Uvicorn workers per container** (and/or more replicas)
  to use all cores; the app is already process-safe (no shared in-proc state).
- **Pagination on remaining list endpoints** (`/watchlists`, `/alerts`) for
  users who accumulate many — same `page`/`size` pattern already used elsewhere.

## Bottlenecks & mitigations (summary)

| Hot path | Risk at scale | Mitigation in place | Next step |
|---|---|---|---|
| Token price reads | CoinGecko latency/limits | Redis read-through cache (TTL) | cache warming + stampede lock |
| Auth endpoints | brute force / abuse | Redis-backed rate limiting | edge gateway tiers |
| Ownership reads | row growth | indexed `user_id` filters + pagination | read replicas |
| API throughput | single process | stateless + container replicas | Gunicorn workers + autoscale |
