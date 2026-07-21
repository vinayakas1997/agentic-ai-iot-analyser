# EDAS Frontend

React dashboard for submitting tasks and viewing results.

## Prerequisites

- Node.js 18+
- Backend running at http://localhost:7009 (see [../backend/README.md](../backend/README.md))

## Setup

```bash
cd edas/frontend
npm install
```

## Environment

Set in shell or via Docker Compose:

| Variable | Description | Default |
|----------|-------------|---------|
| `VITE_API_URL` | Backend REST base URL | `http://localhost:7009` |
| `VITE_WS_URL` | Backend WebSocket URL | `ws://localhost:7009` |
| `VITE_DEFAULT_USER_ID` | User id when auth disabled | `98765` |

## Run (dev)

```bash
npm run dev -- --host 0.0.0.0 --port 7008
```

Open http://localhost:7008

## Docker

From `edas/`:

```bash
docker compose up frontend
```

## Layout

```
frontend/
├── src/
│   ├── api/         REST client
│   ├── components/  TaskInput, EventFeed, ResultCard, …
│   └── hooks/       useWebSocket
├── index.html
├── vite.config.js
└── package.json
```
