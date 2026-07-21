# Manager Agent — Role, Responsibility & Architecture

## Role & Responsibility

The manager agent is the **user-facing conversational orchestrator** for IoT/manufacturing data analysis. It translates natural-language requests into structured, verifiable analysis plans that downstream agents (Planner → Executor) execute.

It acts as the **"concierge"** — guiding the user from a fuzzy question (e.g., *"show me defect rates on line 3 last month"*) through slot-filling, ambiguity resolution, schema context loading, plan proposal/refinement, and final handoff to the Planner Agent.

---

## How It Handles User Requests — The Full Flow

### Entry Points
| File | Role |
|---|---|
| `api/server.py` | FastAPI app with lifespan |
| `api/routes/manager.py` | `POST /sessions/{id}/messages` — main user message endpoint |
| `agents/manager/cli.py` | Interactive CLI for local testing |

### Per-Turn Orchestration (`session_service.py`)

1. **`run_session_turn()`** — top-level orchestrator called by the API route
2. Loads existing session state from PostgreSQL (`session_db.py`)
3. Calls **`run_manager_agent()`** (`runner.py`) which:
   - Validates the input
   - Builds the default state dict
   - **Invokes `manager_graph.ainvoke(state, config)`** — the LangGraph state machine
4. After the graph returns, saves state back to DB with **optimistic locking** (version check)
5. Appends the turn to chat_history and returns the formatted response

### LangGraph State Machine (`agents/manager/graph.py`)

The core is a LangGraph with **25+ nodes** and conditional routing:

```
inject_reference_time
    → extract_slots (LLM parses user message)
        → resolve_all_lines (DB lookup for line/machine names)
            → sync_session_context (fetch registry schema)
                → explore_aims (LLM proposes/refines analysis plans)
                    → build_plan_message → confirm_plan
                        → save_task_definition → send_to_planner (event bus)
```

**Checkpointer**: `MemorySaver` for in-memory state
**Interrupt points**: Nodes where the graph pauses to wait for user input (e.g., missing slots, plan confirmation)

---

## What Makes It "Smart"

### 1. LLM-Powered Slot Extraction (`nodes/extract.py`)

Uses the **`extract_slots` prompt** (`prompts/extract_slots.md` — 464 lines, 100+ rules + examples) to:
- Parse natural-language messages into structured JSON: `line_mentions`, `time_raw`, `aim_raw`, `scope`
- Classify session intent — distinguishes `fill_slots`, `advisory`, and `meta_question` intents
- Handle clarification when input is ambiguous

### 2. Smart Routing Logic (`agents/manager/routing.py`)

6 router functions control conditional graph flow based on state analysis:

| Router | Logic |
|---|---|
| `route_after_inject` | Detects confirmation words (`go`, `yes`...), routes to `detect_confirm`, `confirm_redirect`, or `extract_slots` |
| `route_after_resolve_all_lines` | Checks sync session needs, multi-line errors, missing lines, explore actions |
| `route_after_sync_session_context` | Checks for reuse, meta questions, advisory intents |
| `route_after_time` | Checks if time needs clarification, if missing fields exist |
| `route_after_confirm` | Routes to `save_task_definition` if confirmed, else back to `extract_slots` |

### 3. Multi-Line Resolution (`nodes/multi_line.py`, `slot_inventory.py`)

- Resolves multiple line mentions in a single message
- Handles ambiguous matches (e.g., "line 3" matching multiple DB entries) by asking user to pick
- Builds per-line slot inventories with Q&A generation for missing fields
- Supports different scope types: single-line, all-lines, cross-machine comparison

### 4. Time Resolution (`time_resolution.py`)

- Uses an LLM to normalize fuzzy time phrases ("last week", "jan 5 to jan 7", "early this month") into precise calendar dates
- Has mock mode for testing
- Validates LLM output with strict rules
- Handles relative dates, absolute dates, ambiguous phrases, and invalid input
- Retries once on validation failure

### 5. AI Resilience & Observability (`llm_client.py`)

- **Retry with exponential backoff** — automatic retry on transient failures
- **Circuit breaker** — opens after N consecutive failures, resets after timeout
- **Concurrency-safe** — `asyncio.Lock` prevents race conditions
- **Observability** — tracks latencies, error rates, token estimates per call
- **Tracer integration** — every LLM call is hooked for debugging

### 6. Context & Schema Management (`registry_context.py` — 572 lines)

- Fetches production line bundles from `GlobalRegistry` (DB)
- Applies dataset include/exclude policy
- Builds `line_context` with full schema, column previews, join catalog, suggested aims
- Handles multi-line vs single-line scope
- Caches context in state to avoid repeated DB fetches

### 7. Plan Exploration & Refinement (`nodes/explore_aims.py`)

- Generates **3 structured analysis proposals** per LLM call using `propose_analysis_plans.md` prompt
- Supports **refine** actions — user can keep certain plans, modify others
- Merges refined proposals intelligently (keeping existing selections, updating changed ones)
- Tracks previously seen proposals to avoid repetition
- Max exploration limit of 4 iterations before forcing a decision

### 8. Session Memory & State Management

| Capability | How |
|---|---|
| **PostgreSQL persistence** | Full state JSON stored per session with version-based optimistic locking |
| **Chat windowing** | Returns last N turn-pairs (default 6) for LLM context — prevents token overflow |
| **Session fork** | Deep-copies a session + chat history into a new session for exploring alternatives |
| **Session reopen** | Reopens a completed session back to "plan" phase |
| **Saved plans** | Users can save analysis plans by name, list them, combine/merge them, or activate prior ones |
| **Task reuse** | When user references a prior analysis, loads the saved task definition automatically |

### 9. Meta & Advisory Q&A

The manager can answer **11 categories** of questions without derailing the main flow:
- "What tables are loaded?"
- "What datasets are available for line X?"
- "What are the benefits of this type of analysis?"
- "What should I do next?"

### 10. Robust LLM-JSON Parsing (`json_parse.py`)

Strict JSON extraction from LLM responses with recovery strategies for malformed output (markdown code fences, trailing commas, nested JSON strings, etc.).

---

## Sub-Agents It Coordinates

The manager hands off the final task definition to downstream agents via a **DB-backed event bus**:

| Agent | File | Role |
|---|---|---|
| **Planner Agent** | `agents/planner_agent.py` | Receives structured task definition, generates pandas queries using LLM, handles retries (max 3) |
| **Executor Agent** | `agents/executor_agent.py` | Loads data via `DataHandler`, executes pandas queries, publishes results |

### Event Bus Topics Published by Manager
- `planner.start` — with task definition, schema payload, time range, datasets, saved plan

### WebSocket Events Broadcast to Frontend
`task.new`, `planner.start`, `executor.run`, `planner.result`, `planner.retry`, `manager.result`, `task.complete`, `task.failed`, `manager.line_resolved`, `manager.time_resolved`, `manager.context_synced`, `manager.plan_built`

---

## Simplified End-to-End Flow

```
User (WebSocket / REST)
    │
    ▼
api/server.py (FastAPI)  →  api/routes/manager.py (POST /sessions/{id}/messages)
    │
    ▼
session_service.py (run_session_turn)
    │  ┌────────────────────────────────────────────┐
    │  │  1. Load session from PostgreSQL           │
    │  │  2. Call run_manager_agent()               │
    │  │  3. Invoke LangGraph state machine          │
    │  │  4. Save state back to DB (optimistic lock) │
    │  │  5. Append turn to chat_history             │
    │  └────────────────────────────────────────────┘
    │
    ▼
LangGraph State Machine (25+ nodes)
    │
    ├── inject_reference_time
    ├── extract_slots (LLM: parse user message → structured slots)
    ├── resolve_all_lines (DB: look up line/machine names)
    ├── sync_session_context (Registry: fetch schema + datasets)
    ├── explore_aims (LLM: propose 3 analysis plans)
    ├── build_plan_message → confirm_plan (user approves/refines)
    ├── save_task_definition
    └── send_to_planner (Event Bus: publish planner.start)
        │
        ▼
    Planner Agent (generates pandas queries)
        │
        ▼
    Executor Agent (runs queries on actual data)
        │
        ▼
    Results → WebSocket → Frontend
```

---

## Key Files Reference

| File | Lines | Role |
|---|---|---|
| `agents/manager/graph.py` | 383 | Core LangGraph state machine with 25+ nodes |
| `agents/manager/routing.py` | 425 | 6 conditional router functions |
| `agents/manager/llm_client.py` | 191 | LLM client with retry, circuit-breaker, observability |
| `agents/manager/nodes/extract.py` | 485 | Slot extraction from user messages (LLM-powered) |
| `agents/manager/nodes/explore_aims.py` | 552 | Propose/refine analysis plans via LLM |
| `agents/manager/nodes/plan.py` | 391 | Plan confirmation, save task def, send to planner |
| `agents/manager/registry_context.py` | 572 | Schema fetch, dataset policy, line context building |
| `agents/manager/session_db.py` | 444 | PostgreSQL CRUD with optimistic locking |
| `agents/manager/session_store.py` | 276 | State serialization, snapshot building |
| `agents/manager/slot_inventory.py` | 824 | Multi-line slot management |
| `agents/manager/time_resolution.py` | 472 | Time phrase → calendar date normalization |
| `agents/manager/session_service.py` | 116 | Top-level turn orchestration |
| `agents/manager/runner.py` | 142 | Per-turn graph invocation |
| `agents/manager/state.py` | 103 | `ManagerState` TypedDict |
| `agents/planner_agent.py` | 171 | Downstream planner: generates pandas queries |
| `agents/executor_agent.py` | 76 | Downstream executor: runs queries on data |
| `bus/publisher.py` | 41 | DB-backed event bus publisher |
| `bus/subscriber.py` | 39 | Event bus subscriber with semaphore concurrency |
| `db/models.py` | 117 | SQLAlchemy models (ManagerSession, etc.) |
| `prompts/extract_slots.md` | 464 | Slot extraction prompt (100+ rules) |
| `prompts/propose_analysis_plans.md` | 63 | Plan generation prompt |
| `prompts/normalize_time.md` | — | Time normalization prompt |


--------------------------------------------------------------
over all explanation 
Role & Responsibility
The manager agent is the user-facing "concierge" for IoT/manufacturing data analysis. It takes a fuzzy natural-language request (e.g., "show me defect rates on line 3 last month") and turns it into a verified, executable analysis plan that downstream agents (Planner → Executor) can run.
How It Works
1. Slot-filling conversation — It extracts 3 key pieces of info from the user:
- Line/Machine (what production asset)
- Time range (when)
- Analysis aim (what to analyze)
If any are missing, it asks clarifying questions before proceeding.
2. LangGraph state machine (graph.py) — A graph with 25+ nodes connected by conditional routers. Each turn moves through stages:
- Inject time → Extract slots → Resolve lines → Sync context → Explore/refine aims → Propose plans → Confirm → Hand off to planner
3. LLM-powered intelligence — Every critical decision uses a carefully engineered prompt:
- extract_slots.md (464 lines) — Parses user messages into structured slots with 100+ rules for handling ambiguity, multi-line mentions, and domain-specific language
- propose_analysis_plans.md — Generates 3 structured analysis proposals with specific datasets, joins, and aims
- normalize_time.md — Converts fuzzy time phrases ("last week", "early Jan") to actual calendar dates
What Makes It "Smart"
Capability	How
Ambiguity handling	Detects when a line name is ambiguous (multiple matches) and asks the user to pick
Multi-line scope	Can resolve several machines simultaneously, build cross-machine analysis plans
Context caching	Loads registry schema + past task definitions; avoids redundant DB calls
Plan refinement	Users can say "keep plan 1, change plan 3" and it intelligently merges (up to 4 iterations)
Resilience	LLM client has exponential backoff retry + circuit breaker + concurrency lock
Optimistic locking	Session state version-checked on every save — no lost updates
Session fork/reopen	Users can fork a completed session to explore alternative paths, or reopen a past session
Meta & advisory Q&A	Answers questions like "what tables are loaded?" or "what are the benefits of this analysis?" without derailing the flow
Saved plans	Users can save analysis plans by name, list them, combine them, or activate prior ones
Event bus handoff	Publishes planner.start event; downstream agents pick it up asynchronously with retry semantics
The Flow (Simplified)
User message → Extract slots → Resolve line names (DB lookup)
  → Sync schema context → Propose analysis plans (LLM)
    → User refines/confirms → Save task definition
      → Publish to Planner Agent (event bus) → Executor Agent runs queries
Downstream, the Planner Agent receives the structured task and generates pandas queries, then the Executor Agent runs them against the actual data — all asynchronously via a DB-backed event bus with WebSocket progress updates to the frontend.