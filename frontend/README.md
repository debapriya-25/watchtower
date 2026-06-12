# Watchtower — Frontend

A thin React (Vite) single-page app for the Watchtower API: authentication, a
watchlists dashboard with live prices, price-alert management, and an
admin-gated user view. Function over polish — plain CSS, no UI libraries.

Stack: **React + Vite**, **React Router**, **Axios**, plain CSS. No Redux/
Zustand/Tailwind/component libraries.

## Prerequisites

- Node 20+ and npm.
- The Watchtower backend running (see the root [`README.md`](../README.md));
  default API base is `http://localhost:8000`.

## Setup & run (dev)

```bash
cd frontend
npm install
cp .env.example .env          # optional; defaults to http://localhost:8000
npm run dev                   # http://localhost:5173
```

The backend's CORS already allows `http://localhost:5173` out of the box.

## Configuration

One environment variable (Vite injects `VITE_*` at build time):

| Variable | Default | Purpose |
|---|---|---|
| `VITE_API_BASE` | `http://localhost:8000` | Base URL of the backend API |

## Build & preview (production)

```bash
npm run build                 # outputs static assets to dist/
npm run preview               # serve the production build locally
```

`dist/` is a static bundle — deploy it to any static host (e.g. Vercel,
Netlify, GitHub Pages).

## Features

| Route | What it does |
|---|---|
| `/login`, `/register` | Email/password auth; success/error toasts from API responses |
| `/dashboard` | List / create / rename / delete watchlists (owner-scoped) |
| `/watchlists/:id` | Add/remove catalogue tokens; live price per token (cached vs live badge) |
| `/alerts` | Create / list / delete alerts; activate / deactivate; ABOVE/BELOW + target price |
| `/admin` | **Admin-only** — list users, activate/deactivate (hidden + route-guarded for non-admins) |

## How it works

- **Auth & tokens** — `src/api/client.js` stores the access + refresh JWTs in
  `localStorage`, attaches `Authorization: Bearer <access>` to every request,
  and **transparently refreshes** on a 401 (the backend rotates refresh tokens).
  If refresh fails the session is cleared and the user is redirected to login.
- **Envelope** — every response is unwrapped from `{ success, data, error }`;
  API errors surface as toasts using the backend's `error.message`.
- **Routing** — `ProtectedRoute` redirects unauthenticated users to `/login`
  and non-admins away from `/admin`.
- **State** — local React state + two small contexts (`AuthContext`,
  `ToastContext`); no global state library.

## Project layout

```
src/
├── api/
│   ├── client.js        # axios instance, token attach, 401-refresh, envelope unwrap
│   └── endpoints.js     # AuthAPI / TokensAPI / WatchlistsAPI / AlertsAPI / AdminAPI
├── context/
│   ├── AuthContext.jsx  # user + login/register/logout, localStorage persistence
│   └── ToastContext.jsx # success/error/info toasts
├── components/
│   ├── Navbar.jsx
│   └── ProtectedRoute.jsx
├── pages/
│   ├── Login.jsx · Register.jsx
│   ├── Dashboard.jsx · WatchlistDetail.jsx
│   ├── Alerts.jsx · Admin.jsx
├── App.jsx              # routes
├── main.jsx             # providers + router
└── index.css            # all styling (plain CSS)
```

## Deploy (Vercel example)

1. Import the repo in Vercel; set **Root Directory** to `frontend/`.
2. Build command `npm run build`, output directory `dist`.
3. Set env var `VITE_API_BASE` to your deployed API origin
   (e.g. `https://watchtower-api.onrender.com`).
4. Add the Vercel domain to the backend's `CORS_ORIGINS` and redeploy the API.

Demo logins (after seeding the backend): `demo@watchtower.dev` /
`ChangeMeDemo123!` and `admin@watchtower.dev` / `ChangeMeAdmin123!`.
