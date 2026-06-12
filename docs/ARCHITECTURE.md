# Watchtower — Architecture

A FastAPI backend that serves a crypto **watchlist & price-alert** API, backed by
PostgreSQL (system of record) and Redis (price cache + rate-limit store), with
CoinGecko as the external price feed.

## System context

```mermaid
flowchart LR
    client["Client<br/>(Swagger UI / curl / frontend)"]

    subgraph stack["Docker Compose stack"]
        api["backend<br/>FastAPI + Uvicorn<br/>(non-root, healthchecked)"]
        pg[("PostgreSQL 16<br/>volume: pgdata")]
        redis[("Redis 7<br/>volume: redisdata")]
    end

    coingecko["CoinGecko API<br/>(external price feed)"]

    client -->|"HTTPS / JWT Bearer"| api
    api -->|"SQLAlchemy 2.0 async<br/>(psycopg)"| pg
    api -->|"price cache + rate limits"| redis
    api -->|"read-through on cache miss"| coingecko
```

## Request lifecycle (layers)

```mermaid
flowchart TD
    req["HTTP request"] --> mw["Middleware<br/>CORS + SlowAPI rate limit"]
    mw --> route["Router<br/>auth / tokens / watchlists / alerts / admin / health"]
    route --> deps["Dependencies<br/>get_current_user · require_admin · get_db · get_redis"]
    deps --> svc["Service layer<br/>auth / token / watchlist / alert / admin / coingecko"]
    svc --> data["Data<br/>SQLAlchemy models  ·  Redis  ·  CoinGecko client"]
    data --> env["Response envelope<br/>{ success, data, error }"]
    env --> resp["HTTP response"]

    route -.->|raises AppError / HTTPException| eh["Global exception handlers"]
    eh --> env
```

## Authentication & RBAC

```mermaid
sequenceDiagram
    autonumber
    participant C as Client
    participant A as API (/auth)
    participant DB as PostgreSQL

    C->>A: POST /auth/register or /auth/login (email, password)
    A->>DB: verify / create user (Argon2 hash)
    A->>DB: persist refresh-token jti (refresh_tokens)
    A-->>C: access (15m) + refresh (7d) JWT

    C->>A: GET protected route (Authorization: Bearer access)
    A->>A: get_current_user → decode JWT, load user
    A->>A: require_admin (admin-only routes) → 403 if not admin
    A-->>C: { success, data, error }

    C->>A: POST /auth/refresh (refresh token)
    A->>DB: validate jti (not revoked/expired) → rotate (revoke old, issue new)
    A-->>C: new access + refresh
```

## Data model

```mermaid
erDiagram
    USERS ||--o{ REFRESH_TOKENS : has
    USERS ||--o{ WATCHLISTS : owns
    USERS ||--o{ ALERTS : owns
    WATCHLISTS ||--o{ WATCHLIST_ITEMS : contains
    TOKENS ||--o{ WATCHLIST_ITEMS : referenced_by
    TOKENS ||--o{ ALERTS : referenced_by

    USERS {
        uuid id PK
        string email UK
        string hashed_password
        string full_name
        enum role "user | admin"
        bool is_active
        timestamptz created_at
        timestamptz updated_at
    }
    REFRESH_TOKENS {
        uuid id PK
        uuid user_id FK
        string jti UK
        timestamptz expires_at
        bool revoked
    }
    TOKENS {
        uuid id PK
        string symbol
        string name
        string coingecko_id UK
        bool is_active
    }
    WATCHLISTS {
        uuid id PK
        uuid user_id FK
        string name "unique per user"
    }
    WATCHLIST_ITEMS {
        uuid id PK
        uuid watchlist_id FK
        uuid token_id FK
    }
    ALERTS {
        uuid id PK
        uuid user_id FK
        uuid token_id FK
        numeric target_price
        enum condition "ABOVE | BELOW"
        bool is_active
        timestamptz triggered_at
    }
```

## Price read-through cache

```mermaid
flowchart TD
    start["GET /api/v1/tokens/{id}/price"] --> lookup["Look up token (DB)"]
    lookup --> hit{"Redis key<br/>price:{coingecko_id}:{ccy}?"}
    hit -->|hit| ret1["return payload (cached: true)"]
    hit -->|miss| fetch["CoinGecko GET /simple/price<br/>(timeout + retries)"]
    fetch --> store["SET key, TTL = PRICE_CACHE_TTL_SEC"]
    store --> ret2["return payload (cached: false)"]
```

## Component overview

| Layer | Modules | Responsibility |
|---|---|---|
| Routers | `app/routers/{auth,tokens,watchlists,alerts,admin,health}.py` | HTTP surface, validation, envelope responses, OpenAPI docs |
| Dependencies | `app/deps/auth.py` | `get_current_user`, `require_admin` (RBAC), DB/Redis injection |
| Services | `app/services/*` | Business logic (auth, token catalogue + cache, watchlists, alerts, admin, CoinGecko client) |
| Models | `app/models/*` | SQLAlchemy 2.0 ORM (`User`, `RefreshToken`, `Token`, `Watchlist`, `WatchlistItem`, `Alert`) |
| Schemas | `app/schemas/*` | Pydantic v2 request/response models + envelope |
| Core | `app/core/*` | config, structured logging, security (Argon2/JWT), rate limiting, exceptions, response envelope |
| Data | PostgreSQL, Redis | system of record; cache + rate-limit storage |
| Migrations | `alembic/` | schema versioning (`alembic upgrade head` on container start) |

All endpoints return the standard envelope `{ "success", "data", "error" }`
(the OAuth2 `/auth/token` endpoint is the one intentional exception — it returns
the raw token shape Swagger's *Authorize* flow requires).

See [`../SCALABILITY.md`](../SCALABILITY.md) for scaling strategy and
[`DEPLOYMENT.md`](DEPLOYMENT.md) for running locally and in production.
