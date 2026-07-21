# EDA Data Analysis System — Project Definition

## Project Name
**EDAS — Event Driven Analysis System**

---

## Project Aim
Build a multi-user, event-driven data analysis system where autonomous agents
collaborate via a message bus to analyze data from multiple sources, with results
streamed live to a React dashboard — all isolated per user.

---

## Core Philosophy
- Every component is a **subscriber or publisher** — nothing is hardwired
- Agents are **decoupled** — they don't know about each other, only topics
- User identity (`user_id`) travels inside every message from start to finish
- **Right-sized compute** — big model for thinking, no model for execution
- **Async first** — nothing blocks, everything reacts

---

## Architecture Overview

```
User (React Dashboard)
        ↓ HTTP POST /task
FastAPI Server
        ↓ INSERT into events table
PostgreSQL Events Queue (message bus)
        ↓
┌───────────────────────────────────────┐
│           Agent Workers               │
│                                       │
│  Manager Agent   (topic: task.new)    │
│       ↓                               │
│  Research Agent  (topic: research.start)│
│       ↓  ↑ retry loop                 │
│  Executor Agent  (topic: executor.run)│
└───────────────────────────────────────┘
        ↓ publish to task.complete
┌───────────────────────────────────────┐
│         Subscribers                   │
│  DB Subscriber  → saves to pg         │
│  WS Server      → pushes to frontend  │
└───────────────────────────────────────┘
        ↓
React Dashboard (per user filtered view)
```

---

## File Structure

```
edas/
│
├── PROJECT_DEFINITION.md          # this file
│
├── docker-compose.yml             # PostgreSQL + Redis + backend
├── .env                           # DB_URL, VLLM_URL, SECRET_KEY
├── requirements.txt
│
├── bus/
│   ├── __init__.py
│   ├── publisher.py               # publish(topic, user_id, payload, execute_at=None)
│   ├── subscriber.py              # subscribe(topic, handler, concurrency_limit)
│   └── schemas.py                 # Event pydantic model
│
├── agents/
│   ├── __init__.py
│   ├── manager_agent.py           # breaks task into plan, gives final summary
│   ├── research_agent.py          # plans queries, reflects on failures, retries
│   └── executor_agent.py          # runs SQL/pandas, catches errors, reports back
│
├── data/
│   ├── __init__.py
│   ├── data_handler.py            # unified interface: CSV loader + pg fetcher
│   ├── csv_handler.py             # reads CSV files, returns dataframe
│   └── pg_handler.py              # pg connection, runs SELECT queries
│
├── llm/
│   ├── __init__.py
│   └── client.py                  # vLLM client wrapper (OpenAI compatible)
│                                  # points to DGX Spark local endpoint
│
├── db/
│   ├── __init__.py
│   ├── models.py                  # SQLAlchemy table definitions
│   ├── migrations/
│   │   └── 001_initial.sql        # events, results, chat_history tables
│   └── db_subscriber.py          # listens on task.complete, saves results to pg
│
├── api/
│   ├── __init__.py
│   ├── server.py                  # FastAPI app entry point
│   ├── routes/
│   │   ├── tasks.py               # POST /task, GET /tasks/{user_id}
│   │   └── results.py             # GET /results/{user_id}
│   └── websocket.py               # WS /ws/{user_id} — live result push
│
├── scheduler/
│   ├── __init__.py
│   └── worker_loop.py             # polls events table every N seconds
│                                  # routes pending events to correct agent
│                                  # handles execute_at (scheduled/delayed events)
│                                  # cleans up expired/done events
│
└── frontend/
    ├── package.json
    ├── vite.config.js
    └── src/
        ├── main.jsx
        ├── App.jsx
        ├── api/
        │   └── client.js          # axios wrapper for backend calls
        ├── hooks/
        │   └── useWebSocket.js    # WS connection, filters by user_id
        └── components/
            ├── TaskInput.jsx      # user types analysis task
            ├── EventFeed.jsx      # live feed of all events for this user
            ├── ResultCard.jsx     # final analysis result display
            └── StatusBadge.jsx    # pending / running / done / failed
```

---

## Database Tables

```sql
-- core message bus
CREATE TABLE events (
    id            SERIAL PRIMARY KEY,
    event_id      UUID DEFAULT gen_random_uuid(),
    topic         TEXT NOT NULL,
    user_id       TEXT NOT NULL,
    session_id    TEXT,
    payload       JSONB NOT NULL,
    status        TEXT DEFAULT 'pending',  -- pending | running | done | failed
    consumed_by   TEXT,                    -- which agent picked it up
    attempt       INT DEFAULT 0,           -- retry count
    execute_at    TIMESTAMPTZ DEFAULT NOW(), -- scheduled time
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    updated_at    TIMESTAMPTZ DEFAULT NOW()
);

-- final results per user
CREATE TABLE results (
    id          SERIAL PRIMARY KEY,
    user_id     TEXT NOT NULL,
    session_id  TEXT,
    event_id    UUID,
    task        TEXT,
    result      JSONB,
    status      TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- chat history per user
CREATE TABLE chat_history (
    id          SERIAL PRIMARY KEY,
    user_id     TEXT NOT NULL,
    session_id  TEXT,
    role        TEXT,   -- user | agent
    content     TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
```

---

## Topics (Message Bus Channels)

| Topic | Publisher | Subscriber | Purpose |
|---|---|---|---|
| `task.new` | FastAPI | Manager Agent | new user task arrives |
| `research.start` | Manager Agent | Research Agent | plan queries for task |
| `executor.run` | Research Agent | Executor Agent | run a specific query |
| `research.retry` | Executor Agent | Research Agent | query failed, replan |
| `research.result` | Executor Agent | Research Agent | query succeeded |
| `manager.result` | Research Agent | Manager Agent | all queries done |
| `task.complete` | Manager Agent | DB Subscriber + WS | final result ready |
| `task.failed` | Manager Agent | DB Subscriber + WS | task could not complete |

---

## Agent Definitions

### Manager Agent
- **Model**: Qwen3.5-35B via Atlas (DGX Spark)
- **Concurrency limit**: 5
- **Subscribes to**: `task.new`, `manager.result`
- **Publishes to**: `research.start`, `task.complete`, `task.failed`
- **Responsibility**:
  - Understand user intent
  - Break task into execution plan
  - Receive final results from Research Agent
  - Summarize and publish final answer
  - Decide when to give up (max retries hit)

### Research Agent
- **Model**: GLM-4.7-Flash via vLLM (DGX Spark)
- **Concurrency limit**: 2
- **Subscribes to**: `research.start`, `research.retry`
- **Publishes to**: `executor.run`, `manager.result`
- **Responsibility**:
  - Plan 3-4 evaluation queries for the task
  - Receive errors from Executor
  - Analyze error, reformulate query
  - Retry up to max_retries (3)
  - Report back to Manager when done

### Executor Agent
- **Model**: None (pure Python)
- **Concurrency limit**: 10
- **Subscribes to**: `executor.run`
- **Publishes to**: `research.result`, `research.retry`
- **Responsibility**:
  - Receive query (SQL or pandas)
  - Run against data source via DataHandler
  - On success → publish result
  - On error → catch full error, publish with details
  - No thinking, no LLM, just execute

---

## Data Handler

```python
# unified interface — agents don't care where data comes from
class DataHandler:
    def load(self, source: str) -> pd.DataFrame:
        if source.endswith(".csv"):
            return CSVHandler.load(source)
        else:
            return PGHandler.fetch(source)

    def run_query(self, df: pd.DataFrame, query: str) -> dict:
        # pandas query or SQL depending on source
```

---

## Worker Loop (Scheduler)

```
every 1 second:
  1. SELECT pending events WHERE execute_at <= NOW()
  2. match topic → route to correct agent
  3. mark as running, set consumed_by
  4. agent processes async
  5. mark as done or failed
  6. DELETE events older than 24hrs with status done
```

---

## Concurrency Control

```python
# per agent semaphore
MANAGER_LIMIT  = asyncio.Semaphore(5)
RESEARCH_LIMIT = asyncio.Semaphore(2)
EXECUTOR_LIMIT = asyncio.Semaphore(10)
```

---

## Event Timing Types

| Type | How |
|---|---|
| Immediate | `execute_at = NOW()` |
| Delayed retry | `execute_at = NOW() + interval '30 seconds'` |
| Scheduled | `execute_at = '2026-06-19 09:00:00+09'` |

---

## LLM Configuration

```env
VLLM_BASE_URL=http://192.168.1.101:8009/v1
MANAGER_MODEL=qwen3.5-35b           # Atlas endpoint
RESEARCH_MODEL=glm-4.7-flash        # vLLM endpoint
MAX_TOKENS=2048
TEMPERATURE=0.1
```

---

## Frontend Behavior

- User logs in → gets `user_id`
- Submits task via `TaskInput`
- WebSocket connects to `/ws/{user_id}`
- `EventFeed` shows live agent activity (topic + status updates)
- `ResultCard` renders final answer when `task.complete` arrives
- All data filtered by `user_id` — users never see each other's data

---

## Build Order (for Cursor)

```
Phase 1 — Foundation
  1. docker-compose.yml (pg + backend skeleton)
  2. db/migrations/001_initial.sql
  3. bus/publisher.py + bus/subscriber.py
  4. scheduler/worker_loop.py

Phase 2 — Agents
  5. data/data_handler.py + csv_handler.py + pg_handler.py
  6. llm/client.py
  7. agents/executor_agent.py
  8. agents/research_agent.py
  9. agents/manager_agent.py

Phase 3 — API + Persistence
  10. api/server.py + routes/tasks.py + routes/results.py
  11. api/websocket.py
  12. db/db_subscriber.py

Phase 4 — Frontend
  13. frontend scaffold (Vite + React)
  14. useWebSocket.js hook
  15. TaskInput + EventFeed + ResultCard components
```

---

## Success Criteria
- [ ] 5 simultaneous users can submit tasks without interference
- [ ] Each user sees only their own results on dashboard
- [ ] Executor errors are caught, Research Agent retries automatically
- [ ] Scheduled events fire at correct time
- [ ] DB Subscriber saves all results independently without blocking agents
- [ ] Adding a new agent requires zero changes to existing agents
