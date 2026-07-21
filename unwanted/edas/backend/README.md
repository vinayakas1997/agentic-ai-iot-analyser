# EDAS Backend

Python API, event bus, agents, and database layer.

## Prerequisites

- Remote PostgreSQL at `192.168.1.101:9001` (see [../infra/README.md](../infra/README.md))
- Atlas LLM (`atlas-35b`) at `192.168.1.101:8009` (see [../infra/llm_model.yml](../infra/llm_model.yml))
- Python 3.12+ (local) or Docker via [../docker-compose.yml](../docker-compose.yml)

## Setup

```bash
cd edas/backend
cp .env.example .env   # set DB_URL, VLLM_BASE_URL, MANAGER_MODEL, RESEARCH_MODEL

python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

## Database migrations

Run from `edas/backend/`:

```bash
python -m db.run_migration 001_initial.sql
python -m db.run_migration 002_manager_registries.sql
python -m db.run_migration 003_manager_tables_fresh.sql
python -m db.run_migration 004_test_fruits.sql
python -m db.run_migration 005_drop_schema_registry.sql
python -m db.seed_fruits_global   # optional FRUITS_TEST sample data
```

## Run API

```bash
uvicorn api.server:app --host 0.0.0.0 --port 7009 --reload
```

- Health: http://localhost:7009/health
- Config: http://localhost:7009/config

## Manager Agent CLI

```bash
python -m agents.manager
python -m agents.manager.smoke_test
```

Set `DEBUG=true` in `.env` to print each graph step to the console. Set `NO_PROXY=192.168.1.101,localhost,127.0.0.1` to bypass corporate proxy for LAN LLM/DB.

## Layout

```
backend/
├── api/           FastAPI + WebSocket
├── agents/        Manager, Research, Executor
├── bus/           PostgreSQL message bus
├── scheduler/     Worker poll loop
├── db/            Models, migrations
├── data/          CSV / PG data handlers
├── llm/           OpenAI-compatible client (Atlas)
├── config.py
└── requirements.txt
```

## Verify LLM (from dev machine)

```powershell
$body = @{
  model = "atlas-35b"
  messages = @(@{ role = "user"; content = "Say OK" })
  max_tokens = 10
} | ConvertTo-Json -Depth 5

Invoke-RestMethod -Uri "http://192.168.1.101:8009/v1/chat/completions" `
  -Method POST -Body $body -ContentType "application/json"
```
