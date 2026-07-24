# AGENTS.md — agentic-project Development Guide

## 1. Project Overview

An AI-powered data analysis assistant. Users chat in natural language, the LLM generates SQL queries against PostgreSQL, and results are displayed as tables/charts.

**Tech stack:**
- Backend: Python 3.12 + FastAPI + SQLAlchemy 2.0 (async) + PostgreSQL 16
- Frontend: React 18 + TypeScript + Vite + Zustand + TailwindCSS v4 + Recharts
- LLM: OpenAI-compatible API (vLLM), model configurable via `LLM_MODEL` env var
- Orchestration: Docker Compose (4 services)

---

## 2. Architecture

```
┌──────────┐     :7008      ┌──────────┐     :7010      ┌──────────┐     ┌──────────┐
│ Frontend │ ─────────────→ │  Nginx   │ ────/api/v2───→ │ Backend  │ ──→ │   LLM    │
│  (React) │ ←───────────── │ (proxy)  │ ←────────────── │ (FastAPI)│ ←── │ (vLLM)   │
└──────────┘               └──────────┘                  └────┬─────┘     └──────────┘
                                                              │
                                                              ▼
                                                       ┌──────────┐
                                                       │PostgreSQL│
                                                       │   :5432  │
                                                       └──────────┘
```

**Service network:** All containers on `edas-net` bridge network.
- `db:5432` — PostgreSQL
- `backend:7010` — FastAPI
- `frontend:80` — Nginx serving static files, proxies `/api/` to backend

---

## 3. Rebuild & Restart Rules

### When to rebuild

| Change type | Action | Command |
|-------------|--------|---------|
| Backend `.py` files | Rebuild backend | `cd agentic-project && docker compose build backend && docker compose up -d backend` |
| Frontend `.tsx`/`.ts`/`.css` files | Rebuild frontend | `cd agentic-project && docker compose build frontend && docker compose up -d frontend` |
| Dockerfile or `requirements.txt`/`package.json` changes | Rebuild specific service with `--no-cache` | `docker compose build --no-cache <service> && docker compose up -d <service>` |
| `docker-compose.yml` changes | Full rebuild | `docker compose down && docker compose build && docker compose up -d` |
| `.env` changes (runtime only) | Restart without rebuild | `docker compose restart backend` |
| New mock data / DB schema change | Full reset | `docker compose down -v && docker compose up -d` |

### Port reference

| Service | Internal port | External port |
|---------|--------------|---------------|
| Frontend (Nginx) | 80 | 7008 |
| Backend (FastAPI) | 7010 | 7010 |
| PostgreSQL | 5432 | 5432 |

### Viewing logs

```bash
docker compose logs -f backend    # tail backend logs
docker compose logs -f frontend   # tail frontend logs
docker compose logs db-init       # see one-shot DB seed output
```

---

## 4. Key Files Reference

### Backend (`backend/`)

| File | Purpose |
|------|---------|
| `server.py` | FastAPI app setup, CORS, lifespan, health check |
| `api.py` | All API routes (~1230 lines). Handlers for messages, sessions, queries, datasets |
| `llm_client.py` | LLM prompts (ROUTER, DIRECT, SUGGEST, FOCUS, DEEP), LLM call functions, `parse_numbered_suggestions()` |
| `aims.py` | Chat response gen, SQL gen/criticize/fix, chart suggestions, `extract_aims_from_text()`, `extract_analysis_actions()` |
| `sql_executor.py` | SQL validation, safety checks (SELECT-only), query execution |
| `config.py` | Pydantic-based settings from env vars |
| `resolve.py` | Fuzzy line-name resolution against global_registry |
| `logger.py` | Structured debug logger (levels 0/1/2) |
| `db/models.py` | SQLAlchemy models: `GlobalRegistry`, `TaskRegistry`, `ManagerSession` |
| `db/session.py` | Async SQLAlchemy session factory (asyncpg) |
| `db/init_db.py` | Table creation, seed data (idempotent) |
| `Dockerfile` | `python:3.12-slim`, installs requirements, runs via uvicorn |

### Frontend (`frontend/`)

| File | Purpose |
|------|---------|
| `src/main.tsx` | React entry point with StrictMode + ErrorBoundary |
| `src/App.tsx` | Main layout: Left sidebar (ContextSection) + Center (ChatSection) + Right panel (OutputPanel) |
| `src/sections/ChatSection.tsx` | Main chat UI: dataset search, aim selection, message composer, turn rendering, AIM bar |
| `src/sections/ContextSection.tsx` | Left sidebar: session metadata, dataset attach/detach controls, enrichment toggle |
| `src/sections/OutputPanel.tsx` | Right panel: collected analysis results, context summaries |
| `src/sections/QueryActions.tsx` | Query results as tables or charts (Recharts) |
| `src/components/TurnBubble.tsx` | Chat turn renderer (user message + agent response + analysis actions) |
| `src/components/AimBar.tsx` | Toolbar for selected aims: run, retry, view results, remove |
| `src/components/PreviewModal.tsx` | Modal to preview an aim before adding |
| `src/components/Navbar.tsx` | Top nav with session switcher |
| `src/stores/sessionStore.ts` | Zustand: session lifecycle, turns, aims, enrichment, message sending, polling |
| `src/stores/datasetStore.ts` | Zustand: dataset selection (`selected`) and attachment (`attached`) |
| `src/stores/outputStore.ts` | Zustand: collected analysis results |
| `src/stores/uiStore.ts` | Zustand: selected turn index |
| `src/api/client.ts` | HTTP API client with 409 retry logic |

### Config & Infrastructure

| File | Purpose |
|------|---------|
| `docker-compose.yml` | 4 services: db, db-init, backend, frontend |
| `.env` | Root env vars: `VLLM_BASE_URL`, `LLM_MODEL` |
| `backend/.env.example` | Example backend env vars |
| `mock-database-fill/` | DB seeding service (loads CSVs into mock tables) |

---

## 5. Common Development Tasks

### Add a new API endpoint

1. Add route handler in `backend/api.py` using FastAPI decorator
2. Define Pydantic request/response models in the same file (or import from types)
3. Add client function in `frontend/src/api/client.ts`

### Change an LLM prompt

1. Edit the prompt constant in `backend/llm_client.py`
2. Rebuild backend: `docker compose build backend && docker compose up -d backend`

### Add a new frontend component

1. Create component in `frontend/src/components/` or `frontend/src/sections/`
2. Add Zustand store logic in `frontend/src/stores/` if needed
3. Import types from `frontend/src/types/manager.ts`
4. Rebuild frontend: `docker compose build frontend && docker compose up -d frontend`

### Add a new dataset

1. Add mock data CSV to `mock-database-fill/`
2. Update `mock-database-fill/fill_mock_data.py` to load the CSV
3. Add a `GlobalRegistry` entry in `backend/db/init_db.py`
4. Reset DB: `docker compose down -v && docker compose up -d`

### Reset the database to clean state

```bash
docker compose down -v              # removes volumes
docker compose up -d                 # recreates everything
```

### View backend logs in real-time

```bash
docker compose logs -f backend
```

---

## 6. Code Conventions

### Backend (Python)
- Always use `async/await` (FastAPI + async SQLAlchemy)
- Request/response models use Pydantic `BaseModel`
- Database queries use SQLAlchemy 2.0 async ORM (`AsyncSession`)
- Logger: use `logger` from `logger.py` (not `print`)
- Config: use `get_settings()` from `config.py`
- SQL mutations: run through `sql_executor.py` for safety validation
- Session writes: use optimistic locking via `version` column

### Frontend (TypeScript/React)
- State management: Zustand stores (no Redux, no Context API)
- Components: functional components only (no class components)
- Styling: TailwindCSS utility classes (no CSS modules, no styled-components)
- Types: defined in `src/types/manager.ts` and `src/types/index.ts`
- API calls: through `src/api/client.ts` (handles auth, retries, error handling)
- Icons: inline SVG components in `src/lib/icons.tsx`
- No eslint/prettier configured — match existing code style
- Follow existing component patterns for consistency

### LLM Prompts
- Use numbered lists for structured outputs
- Use `**bold**` for field names in structured formats
- Include explicit formatting examples ("Output in this exact format")
- Use `##` section headers for readability
- Rules sections with bullet points

---

## 7. Environment Variables

| Variable | Default | Service | Description |
|----------|---------|---------|-------------|
| `DB_URL` | `postgresql+asyncpg://manager_agent:manager_agent_pass@db:5432/manager_agent_db` | backend | Database connection |
| `VLLM_BASE_URL` | `http://host.docker.internal:8009/v1` | backend | LLM endpoint |
| `LLM_MODEL` | `qwen36-35B` | backend | Model name |
| `API_HOST` | `0.0.0.0` | backend | Bind address |
| `API_PORT` | `7010` | backend | Bind port |
| `CORS_ORIGINS` | `http://localhost:7008,http://localhost` | backend | Allowed CORS origins |
| `DEBUG` | `false` | backend | Debug mode |
| `LOG_LEVEL` | `0` | backend | 0=off, 1=console, 2=file |
| `VITE_API_URL` | `http://localhost:7010` | frontend (build arg) | Backend API URL |
| `VITE_WS_URL` | `ws://localhost:7009` | frontend (build arg) | WebSocket URL |

---

## 8. API Reference

All endpoints under `/api/v2` prefix.

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/health` | Health check |
| `POST` | `/api/v2/resolve-line` | Fuzzy-match line name |
| `POST` | `/api/v2/aim/new-research` | LLM generates structured aim |
| `POST` | `/api/v2/bucket/proceed` | Save aim to task registry |
| `POST` | `/api/v2/execute-query` | Generate → validate → execute SQL (two-agent loop) |
| `POST` | `/api/v2/sessions` | Create session |
| `GET` | `/api/v2/sessions` | List sessions |
| `GET` | `/api/v2/sessions/{id}` | Get session with turns |
| `PATCH` | `/api/v2/sessions/{id}` | Update session (title, state) |
| `POST` | `/api/v2/messages` | Send chat message (routes to DIRECT/SUGGEST/FOCUS/DEEP) |
| `POST` | `/api/v2/sessions/{id}/summarize-context` | Summarize turns (idempotent) |
| `GET` | `/api/v2/datasets` | List datasets |

### Message Routing Logic

The `/messages` endpoint classifies user questions:

- **DIRECT** — Specific factual question → generates SQL, validates, executes, interprets results
- **SUGGEST** — Exploratory ("what can I do?") → proposes 3 analysis ideas (no SQL)
- **FOCUS** — Deep-dive on one topic → generates SQL, executes, detailed interpretation
- **DEEP** — Multi-step research → loops SQL/execute/interpret up to 3 iterations

### SQL Safety

All SQL queries are validated: SELECT-only, no DROP/DELETE/UPDATE/INSERT, no CROSS JOIN, automatic LIMIT 200.

### Optimistic Locking

Session writes use `version` column. On conflict (409), the client retries with exponential backoff (handled in `api/client.ts`).
