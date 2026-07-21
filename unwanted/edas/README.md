# EDAS — Event Driven Analysis System

EDAS is split into two apps:

| App | Path | Port | Stack |
|-----|------|------|-------|
| **Backend** | [backend/](backend/) | 7009 | FastAPI, agents, PostgreSQL bus |
| **Frontend** | [frontend/](frontend/) | 7008 | React (Vite) dashboard |

Shared deployment notes: [infra/](infra/) (remote Postgres + Atlas LLM).

## Quick start (Docker)

```bash
cd edas
cp backend/.env.example backend/.env   # edit DB_URL, VLLM_BASE_URL, models
docker compose up --build
```

- Dashboard: http://localhost:7008
- API health: http://localhost:7009/health

## Local development

- **Backend:** see [backend/README.md](backend/README.md)
- **Frontend:** see [frontend/README.md](frontend/README.md)

No login in the prototype — dashboard uses `DEFAULT_USER_ID` from backend `.env`.
