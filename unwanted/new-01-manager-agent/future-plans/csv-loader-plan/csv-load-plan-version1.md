# CSV Loader — Integration Plan v1

## Overview

Replace the current PostgreSQL data path (global_registry → PG tables) with a **per-session SQLite** approach. Users upload CSV files, each session gets its own SQLite database, and the executor runs SQL queries against it instead of pandas expressions.

The critical addition is a **Column Clarification Gate** — after upload, the LLM generates human-readable meanings for each column, and the user must confirm/edit them before any analysis proceeds. This locks the schema context once and eliminates guesswork in every downstream step.

### Key Architectural Decisions

| Decision | Choice |
|----------|--------|
| Storage per session | Single SQLite file at `/data/sessions/{session_id}/data.db` |
| Source type marker | `source_type: "pg" | "csv"` in state — drives routing at `merge_slots` |
| Upload gate | Column clarification is a LangGraph interrupt node — must pass before analysis |
| Query language | SQL (planner generates SQL, executor runs via `sqlite3`) |
| Global registry | Skipped when `source_type == "csv"` — schema read dynamically from SQLite file |
| PG infra kept | Event bus, session metadata, chat history, task registry unchanged |
| Upload isolation | Each session's SQLite file is user + session scoped |
| Multiple uploads | All tables shown together in ONE clarification pass, not one by one |
| Column meaning generation | LLM receives first 5 data rows alongside column names for accurate inference |
| Column clarification view | Dedicated full-screen view (not inline in chat). On "All set", user returns to normal chat |

---

## Complete Data Flow

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ 1. UPLOAD PHASE (REST API)                                                  │
│                                                                              │
│ User uploads CSV(s) → POST /sessions/{id}/upload                            │
│         │                                                                    │
│         ▼                                                                    │
│ CSV Pre-checks (validation pipeline)                                         │
│    ├── File extension & size check                                           │
│    ├── Encoding detection                                                    │
│    ├── Header validation                                                     │
│    ├── Row/column consistency                                                │
│    ├── Data type inference                                                   │
│    ├── Null/missing value analysis                                           │
│    ├── Duplicate detection                                                   │
│    └── Multi-file consistency (if multiple CSVs)                             │
│         │                                                                    │
│         ▼                                                                    │
│ Validation report returned to user (pass/fail + warnings)                    │
│         │                                                                    │
│         ▼                                                                    │
│ On pass: CSV → SQLite import                                                │
│    ├── Create /data/sessions/{session_id}/data.db                            │
│    ├── Each CSV → one SQLite table (table name = file stem)                  │
│    ├── Schema inferred from data (dtypes + sampling)                         │
│    ├── Indexes created on key columns                                        │
│    └── CALL update_session_state() to set:                                   │
│         ├── source_type = "csv"                                              │
│         ├── sqlite_db_path = "/data/sessions/{session_id}/data.db"           │
│         └── pending_column_clarification = true                              │
│                                                                              │
│ 2. GRAPH PHASE — LINE RESOLUTION (after merge_slots)                        │
│                                                                              │
│ merge_slots                                                                  │
│      │                                                                       │
│      ├── source_type == "pg"  ──→ resolve_all_lines (existing logic)        │
│      │                             Queries global_registry, resolves line    │
│      │                             Sets slots.line.canonical, resolved=true  │
│      │                                                                       │
│      └── source_type == "csv" ──→ resolve_all_lines (NEW CSV BRANCH)        │
│                                    Reads table name from SQLite file          │
│                                    Sets slots.line.canonical = table_name     │
│                                    Sets slots.line.resolved = true            │
│                                    No global_registry query needed            │
│                                                                              │
│ 3. GRAPH PHASE — COLUMN CLARIFICATION GATE (NEW)                            │
│                                                                              │
│ resolve_all_lines                                                            │
│      │                                                                       │
│      ├── pending_column_clarification == true  ──→ column_clarify            │
│      │                                                │                      │
│      │                                         Reads SQLite file directly    │
│      │                                         Gets column names + 5 rows   │
│      │                                         LLM generates 1-line meaning │
│      │                                         for EACH column              │
│      │                                                │                      │
│      │                                         Opens DEDICATED VIEW:        │
│      │  ┌────────────────┬──────────────────────────────────┐               │
│      │  │ prod_cd        │ Product code identifier           │               │
│      │  │ ord_dt         │ Order date (YYYY-MM-DD)           │               │
│      │  │ qty_shpd       │ Quantity shipped in units         │               │
│      │  │ price          │ Unit price in USD                 │               │
│      │  └────────────────┴──────────────────────────────────┘               │
│      │  User edits any meaning inline → clicks "All set"                     │
│      │                                                │                      │
│      │                                         confirm_col_defs             │
│      │                                         column_definitions LOCKED    │
│      │                                         pending_column_clarification  │
│      │                                         cleared                       │
│      │                                                │                      │
│      └── pending_column_clarification == false ──→ sync_session_context      │
│                                                     (definitions ready)       │
│                                                                              │
│ 4. GRAPH PHASE — SYNC CONTEXT (runs ONCE after clarification)               │
│                                                                              │
│ sync_session_context                                                         │
│    └── source_type == "csv" → reads locked column_definitions from state    │
│    └── Builds line_context with column names + LLM meanings                  │
│    └── No registry queries needed                                            │
│                                                                              │
│ show_suggested_aims                                                          │
│    └── CSV BRANCH: LLM generates suggestions from locked column_definitions │
│    └── User picks/edits an aim → aim is locked                              │
│                                                                              │
│ 5. EXECUTION PHASE                                                          │
│                                                                              │
│ send_to_planner                                                              │
│    └── planner_payload.source_type = "sqlite"                               │
│    └── planner_payload.source_config = {"path": "...", "table": "..."}      │
│    └── planner_payload.dataset_schemas = locked column defs with meaning    │
│                                                                              │
│ Planner Agent (SQL generator)                                                │
│    └── Prompt: "Given schema with meanings, write SQL queries"             │
│    └── Output: ["SELECT ...", "SELECT ..."]                                 │
│                                                                              │
│ Executor Agent                                                               │
│    └── Receives: {data_source: db_path, query: "SELECT ..."}                │
│    └── Uses DataHandler.run_sql(sqlite_path, query)                         │
│                                                                              │
│ DataHandler                                                                  │
│    └── run_sql(path, sql) → sqlite3.connect → cursor.execute               │
│    └── Returns: {"success": true, "data": [...], "rows": N}                │
│                                                                              │
│ 6. RESULT PERSISTENCE (unchanged)                                            │
│    └── Results stored in results table (PG)                                 │
│    └── Broadcast via WebSocket to frontend                                   │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Key Ordering Fix — Why column_clarify runs BEFORE sync_session_context

In the initial plan, `sync_session_context` ran first, then `column_clarify`, then `sync_session_context` again. This was inefficient and confusing.

```
WRONG: sync_session_context → column_clarify → confirm_col_defs → sync_session_context (repeat)
RIGHT: column_clarify → confirm_col_defs → sync_session_context (runs ONCE)
```

**Why the new order is correct:**
- `column_clarify` reads the SQLite file directly — it doesn't need `line_context` or `dataset_context` from `sync_session_context`
- `sync_session_context` runs AFTER definitions are locked — it reads clean, finalized `column_definitions` from state
- No duplicate work, no temp state, no confusion about which pass is which

---

## CSV Pre-checks (Validation Pipeline)

Each uploaded CSV passes through the following checks **before** import. The validation is synchronous and returns a detailed report.

### 1. File-Level Checks

| Check | What | Fail condition |
|-------|------|----------------|
| Extension | Must end with `.csv` | Not `.csv` |
| Size | Max 50 MB per file | Exceeds limit |
| Empty file | At least 1 data row | 0 rows (header only or empty) |
| BOM detection | Strip UTF-8 BOM if present | N/A (auto-fix) |

### 2. Encoding & Parsing

| Check | What | Fail condition |
|-------|------|----------------|
| Encoding detection | `chardet` or `cchardet` to detect encoding | If confidence < 0.8, warn |
| Delimiter detection | Try `,`, `;`, `\t`, `\|` | If ambiguous, reject |
| Quote character | `"` or `'` | If inconsistent, warn |
| Line endings | CRLF / LF consistency | If mixed, warn (auto-fix) |

### 3. Header Validation

| Check | What | Fail condition |
|-------|------|----------------|
| Header exists | First row is column names | No header → reject (require header) |
| Empty column names | Any col name is empty string | Reject |
| Duplicate columns | Same name appears twice | Reject (suffix not allowed) |
| Special characters | Column names contain only `[a-zA-Z0-9_-]` | If unsafe, sanitize + warn |
| Reserved SQL keywords | Col name is SQL reserved word | Warn (auto-quote in SQL) |

### 4. Data Validation

| Check | What | Fail condition |
|-------|------|----------------|
| Row consistency | All rows have same column count | If > 5% rows mismatch, reject |
| Column count stability | Max col count change across rows | Reject (malformed CSV) |
| Type inference | Sample first 1000 rows, infer per-column type | If mixed types > 10% in a col, warn |
| Null percentage | % of nulls per column | If > 80% null, warn; if > 95%, reject column |
| All-null columns | Column where every row is null | Reject column |
| Truncated rows | Last row cut off mid-value | Reject |

### 5. Duplicate Detection

| Check | What | Fail condition |
|-------|------|----------------|
| Exact duplicate rows | All columns identical | Warn with count |
| Near-duplicate rows | Levenshtein distance < 3 on text cols | Warn |
| Primary key candidate | If any col has unique non-null values | Suggest as PK (info only) |

### 6. Multi-File Checks (if uploading 2+ CSVs)

| Check | What | Fail condition |
|-------|------|----------------|
| Cross-file name collisions | Same table name from diff files | Reject (rename required) |
| Join key compatibility | Columns with same name have same type | Warn if type mismatch |
| Referential integrity | Values in one file match values in another | Warn |

### Validation Report Format

```json
{
  "status": "pass" | "fail" | "pass_with_warnings",
  "files": [
    {
      "filename": "sales.csv",
      "rows": 15000,
      "columns": 12,
      "column_definitions": [...],
      "errors": [],
      "warnings": ["Column 'date' has 5% null values"]
    }
  ],
  "summary": {
    "total_files": 1,
    "total_rows": 15000,
    "total_columns": 12,
    "error_count": 0,
    "warning_count": 2
  }
}
```

If `status == "fail"`, data is **not imported** — user must fix and re-upload.

---

## Column Clarification Gate (LangGraph Interrupt Node)

This is the critical gate that all uploaded CSVs must pass through before any analysis can happen. It runs as a LangGraph node with an interrupt point, allowing the user to review and edit before proceeding.

### Node: `column_clarify`

**When it triggers:** The graph checks for `pending_column_clarification == true` in state (set after upload + SQLite import).

**Position in graph:** After `resolve_all_lines`, before `sync_session_context`. If `pending_column_clarification` is true, route to `column_clarify` instead of continuing to `sync_session_context`.

```
resolve_all_lines
      │
      ├── pending == true  ──→ column_clarify (dedicated view opens)
      │                              │
      │                         User edits meanings
      │                              │
      │                         User clicks "All set"
      │                              │
      │                         confirm_col_defs (locks definitions)
      │                              │
      │                         sync_session_context (runs ONCE with locked defs)
      │                              │
      └── pending == false ──→ sync_session_context (normal flow)
```

**Why this order matters:**
- `resolve_all_lines` sets `slots.line` (canonical name, resolved=true) — no dependency on column meanings
- `column_clarify` reads the SQLite file directly — no need for `sync_session_context` to run first
- `sync_session_context` runs AFTER column definitions are locked — it never sees raw/unconfirmed schema
- `sync_session_context` runs exactly ONCE, not twice

**Important UX behavior:**
- Column clarification opens a **dedicated full-screen view** in the frontend (not inline chat editing)
- The dedicated view shows the column table with editable meaning fields
- When user clicks "All set", the view closes and user returns to the normal chat screen
- No chat history is consumed by this step — it's a UI overlay, not a conversation turn

**Node logic:**

```
column_clarify(state) → ManagerState
  1. Read column names + first 5 data rows from SQLite schema
  2. Call LLM with prompt:
       "Given these column names and sample data from table X,
        write a 1-line plain-English description for each column.
        Be specific about units, formats, and codes if inferable from values.
        
        Columns and first 5 data rows:
        {column_name}: {value1, value2, value3, value4, value5}
        ...

        Return JSON: [{\"name\": \"col_name\", \"meaning\": \"...\"}]"
  3. Store LLM output as pending_column_meanings in state
  4. Set phase to "clarify_columns" — frontend detects this and opens dedicated view
  5. Interrupt (interrupt_after) — wait for user confirmation
```

**Multiple CSV files handling:**
- ALL tables are shown together in a single pass (not one by one)
- The dedicated view shows sections for each table
- Example:

```
Table: sales_data
  ┌──────────────┬────────────────────────────────┐
  │ Column Name  │ Meaning                        │
  ├──────────────┼────────────────────────────────┤
  │ prod_cd      │ Product code identifier        │
  │ qty_shpd     │ Quantity shipped in units      │
  └──────────────┴────────────────────────────────┘

Table: inventory
  ┌──────────────┬────────────────────────────────┐
  │ Column Name  │ Meaning                        │
  ├──────────────┼────────────────────────────────┤
  │ warehouse_id │ Warehouse location code        │
  │ stock_level  │ Current stock in units         │
  └──────────────┴────────────────────────────────┘

[Edit any field inline] [All Set]
```

**User response handling:**

When user clicks "All set":
  1. Frontend sends structured payload with edited meanings
  2. `confirm_col_defs` node receives the payload
  3. Merges edits into finalized column_definitions
  4. Clears pending_column_clarification flag
  5. Graph re-enters sync_session_context (which now sees pending=false)
  6. Continues to show_suggested_aims with locked definitions

**Why dedicated view instead of inline chat:**
- Editable table needs rich UI (text inputs per cell) — chat messages are read-only
- Avoids polluting chat history with column clarification turns
- User stays in context, edits everything, returns to chat in one action
- Clean separation between "setup" and "analysis" phases

### Column Definitions Structure (locked in state)

```json
{
  "tables": [
    {
      "table_name": "sales",
      "column_definitions": [
        {"name": "prod_cd",   "datatype": "TEXT", "meaning": "Product code identifier"},
        {"name": "ord_dt",    "datatype": "TEXT", "meaning": "Order date (YYYY-MM-DD)"},
        {"name": "qty_shpd",  "datatype": "INTEGER", "meaning": "Quantity shipped in units"},
        {"name": "price",     "datatype": "REAL", "meaning": "Unit price in USD"}
      ]
    }
  ]
}
```

Once locked, these definitions are used by:
- `show_suggested_aims` — LLM reads column meanings to suggest analysis directions
- `build_plan_message` — user-facing plan includes column descriptions
- `planner_agent` — SQL generation prompt includes column meanings for accurate queries
- Every subsequent graph turn — no re-guessing column semantics

### Benefits of the Gate

| Problem | Solution |
|---------|----------|
| LLM guesses column meaning every time | Meaning is generated once, locked, reused |
| Context drift across turns | Locked defs remain stable for entire session |
| User has no control over LLM interpretation | User can edit any column meaning inline |
| Wrong column interpretation leads to bad SQL | Planner sees accurate column meaning from the start |
| Multi-file ambiguity | Each table goes through its own clarification pass |

---

## SQLite Import Process

```python
async def import_csv_to_sqlite(
    session_id: str,
    csv_files: list[UploadFile],
    validated: list[dict],
) -> str:
    db_dir = f"/data/sessions/{session_id}"
    os.makedirs(db_dir, exist_ok=True)
    db_path = f"{db_dir}/data.db"

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Enable WAL mode for concurrent reads
    cursor.execute("PRAGMA journal_mode=WAL;")

    for file_info in validated:
        df = pd.read_csv(file_info["temp_path"])
        table_name = sanitize_table_name(file_info["filename"])  # e.g. "sales.csv" → "sales"

        # Write to SQLite with inferred types
        df.to_sql(table_name, conn, if_exists="replace", index=False)

        # Create indexes on columns with unique values or join keys
        for col in file_info.get("index_columns", []):
            cursor.execute(
                f"CREATE INDEX IF NOT EXISTS idx_{table_name}_{col} "
                f"ON {table_name} ({col});"
            )

    conn.commit()
    conn.close()
    return db_path
```

---

## Component-by-Component Changes

### 1. New: `api/routes/upload.py`

```python
@router.post("/sessions/{session_id}/upload")
async def upload_csv(
    session_id: str,
    files: list[UploadFile] = File(...),
) -> UploadResponse:
    # 1. Validate session exists and is active
    # 2. Save files to /tmp/{session_id}/ for processing
    # 3. Run pre-check pipeline
    # 4. If pass: import CSV → SQLite, store db_path in session
    # 5. Return validation report
```

### 2. New: `data/csv_validator.py`

```python
class CSVValidator:
    async def validate(self, file_path: str) -> FileValidationResult:
        # Run all pre-checks from the table above
        pass

    async def validate_multi(self, file_paths: list[str]) -> MultiFileValidationResult:
        # Run per-file + cross-file checks
        pass
```

### 3. New: `data/csv_to_sqlite.py`

```python
async def import_csv_to_sqlite(
    session_id: str,
    validated_files: list[ValidatedFile],
) -> str:
    # Creates SQLite, imports each validated CSV as a table
    pass
```

### 4. Modified: `data/data_handler.py`

Add `run_sql()` method. Remove or extend `load()`:

```python
class DataHandler:
    def run_sql(self, db_path: str, sql: str) -> dict:
        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.execute(sql)
            rows = [dict(row) for row in cursor.fetchall()]
            return {"success": True, "data": rows, "rows": len(rows)}
        except Exception as e:
            return {"success": False, "error": str(e), "error_type": type(e).__name__}
        finally:
            conn.close()
```

### 5. Modified: `agents/manager/state.py`

Add fields:

```python
class ManagerState(TypedDict):
    ...
    source_type: str | None                            # NEW — "pg" | "csv" | None. Drives routing at merge_slots
    sqlite_db_path: str | None                         # NEW — path to session's SQLite file
    pending_column_clarification: bool                 # NEW — flag: is column clarify needed
    pending_column_meanings: list[dict] | None         # NEW — LLM-generated meanings before confirm
    column_definitions: list[dict] | None              # NEW — FINAL locked column defs after "All set"
```

### 6. Modified: `agents/manager/nodes/multi_line.py` — `resolve_all_lines` CSV branch

The `resolve_all_lines` node gains a CSV branch. When `source_type == "csv"`, instead of querying `global_registry`, it reads the table name from the SQLite file and sets the line slot directly.

```python
async def resolve_all_lines(state: ManagerState) -> ManagerState:
    if state.get("source_type") == "csv":
        # CSV branch — no global_registry lookup
        db_path = state.get("sqlite_db_path")
        if not db_path:
            return {**state, "error": "no_sqlite_db"}

        # Read table name from SQLite
        import sqlite3
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()

        if not tables:
            return {**state, "error": "no_tables_in_sqlite"}

        table_name = tables[0]  # Primary table (first one)
        slots = dict(state.get("slots") or {})
        slots["line"] = {
            "mention": table_name,
            "canonical": table_name,
            "resolved": True,
            "source": "csv_upload",
            "candidates": [],
        }
        slots["line_slots"] = [{
            "mention": table_name,
            "canonical": table_name,
            "resolved": True,
            "status": "resolved",
            "source": "csv_upload",
            "candidates": [],
            "lookup_locked": True,
        }]
        return {
            **state,
            "slots": slots,
            "missing": compute_missing(slots),
            "error": None,
            "phase": "resolve",
        }

    # ... existing PG logic (global_registry lookup) ...
```

### 7. New: `agents/manager/session_db.py` — `update_session_state()`

The upload REST endpoint needs to update the session's `state_json` in PG with `source_type`, `sqlite_db_path`, `pending_column_clarification`. Currently, no function exists for partial state updates.

```python
async def update_session_state(
    user_id: str,
    session_id: str,
    updates: dict,
) -> None:
    """Partially update the state_json of a session (used by upload endpoint)."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(ManagerSession).where(
                ManagerSession.session_id == session_id,
                ManagerSession.user_id == user_id,
            )
        )
        row = result.scalar_one_or_none()
        if not row:
            raise ValueError("session_not_found")

        # Merge updates into existing state_json
        current = dict(row.state_json or {})
        current.update(updates)
        row.state_json = current
        row.version += 1
        await db.commit()
```

Used by the upload endpoint:

```python
# In POST /sessions/{session_id}/upload:
await update_session_state(user_id, session_id, {
    "source_type": "csv",
    "sqlite_db_path": "/data/sessions/{session_id}/data.db",
    "pending_column_clarification": True,
})
```

### 8. Modified: `agents/manager/db.py` (OR new: `agents/manager/sqlite_db.py`)

Replace registry queries with SQLite schema reader:

```python
async def fetch_sqlite_schema(db_path: str) -> list[dict]:
    """Read schema from SQLite file instead of global_registry."""
    conn = sqlite3.connect(db_path)
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    datasets = []
    for table in tables:
        cursor = conn.execute(f"PRAGMA table_info('{table}')")
        columns = [
            {
                "name": row[1],
                "datatype": row[2] or "TEXT",
                "nullable": not row[3],
                "primary_key": bool(row[5]),
            }
            for row in cursor.fetchall()
        ]
        cursor = conn.execute(f"SELECT COUNT(*) FROM \"{table}\"")
        row_count = cursor.fetchone()[0]
        datasets.append({
            "dataset_name": table,
            "source_type": "sqlite",
            "source_config": {"path": db_path, "table": table},
            "column_definitions": columns,
            "description": f"Uploaded CSV with {row_count} rows, {len(columns)} columns",
            "role": "primary" if len(tables) == 1 or table == tables[0] else "supporting",
        })
    conn.close()
    return datasets
```

### 9. New: `agents/manager/nodes/column_clarify.py`

LangGraph interrupt node for the column clarification gate:

```python
async def column_clarify(state: ManagerState) -> ManagerState:
    """LLM generates column meanings → show table → wait for user to confirm 'All set'."""
    db_path = state.get("sqlite_db_path")
    if not db_path:
        return state

    # Read raw column names from SQLite schema
    conn = sqlite3.connect(db_path)
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]

    pending_meanings = []
    for table in tables:
        cursor = conn.execute(f"PRAGMA table_info('{table}')")
        columns = [{"name": row[1], "datatype": row[2]} for row in cursor.fetchall()]

        # LLM generates meaning for each column
        meanings = await llm_generate_column_meanings(table, columns)
        pending_meanings.append({
            "table_name": table,
            "columns": meanings,  # [{"name": ..., "datatype": ..., "meaning": ...}]
        })
    conn.close()

    # Build structured table for chat display
    table_rows = []
    for entry in pending_meanings:
        for col in entry["columns"]:
            table_rows.append(f"| {col['name']} | {col['meaning']} |")

    agent_message = (
        f"I found the table **{pending_meanings[0]['table_name']}** with these columns.\n\n"
        f"Here's my understanding of each column:\n\n"
        f"| Column | Meaning |\n"
        f"|--------|--------|\n"
        f"{chr(10).join(table_rows)}\n\n"
        f"You can edit any meaning if I got it wrong. Type **'All set'** when ready."
    )

    return {
        **state,
        "pending_column_meanings": pending_meanings,
        "agent_message": agent_message,
        "phase": "clarify_columns",
    }


async def confirm_column_definitions(state: ManagerState) -> ManagerState:
    """User confirmed 'All set' — lock column definitions into state."""
    return {
        **state,
        "column_definitions": state.get("pending_column_meanings"),
        "pending_column_meanings": None,
        "pending_column_clarification": False,
        "phase": "context",
    }
```

### 10. Modified: `agents/manager/graph.py`

Add column_clarify and confirm_column_definitions nodes + source_type conditional at merge_slots:

```python
from agents.manager.nodes.column_clarify import column_clarify, confirm_column_definitions

graph.add_node("column_clarify", column_clarify)
graph.add_node("confirm_col_defs", confirm_column_definitions)

# column_clarify → interrupt → user clicks "All set" → confirm_col_defs → re-enter sync
graph.add_edge("column_clarify", "confirm_col_defs")
graph.add_edge("confirm_col_defs", "sync_session_context")
```

### 12. Modified: `agents/manager/routing.py`

Two routing changes:

**A) After `resolve_all_lines` — CSV mode sets line slot, then checks column clarification:**

For CSV mode, `resolve_all_lines` reads the table name from the SQLite file and sets `slots.line`. Then the router checks if column clarification is needed.

```python
def route_after_resolve_all_lines(state: ManagerState) -> str:
    if state.get("source_type") == "csv" and state.get("pending_column_clarification"):
        # Column clarification needed — open dedicated view
        return "column_clarify"
    # ... existing routing logic (sync_session_context, ask_missing, etc.) ...
```

**B) Inside `resolve_all_lines` — CSV branch (see component 10 below):**

The node itself branches on `source_type` to determine how to resolve the "line". No routing change at `merge_slots` — both PG and CSV go through the same `resolve_all_lines` node.

### 13. Modified: `agents/manager/registry_context.py`

The `sync_dataset_context_for_state` function accepts a `fetch_fn` parameter. Inject `fetch_sqlite_schema` instead of `fetch_global_datasets`. The flow:

```python
# In sync_session_context node:
if state.get("sqlite_db_path"):
    # Use SQLite path
    fetch_fn = lambda line: {
        "line_name": line,
        "datasets": await fetch_sqlite_schema(state["sqlite_db_path"]),
        ...
    }
else:
    # Fall back to PG registry
    fetch_fn = fetch_line_bundle
```

### 14. Modified: `agents/manager/nodes/plan.py` — `send_to_planner()`

Update payload to include SQLite path:

```python
payload = {
    ...
    "source_type": "sqlite",
    "source_config": {"path": state.get("sqlite_db_path"), "table": table_name},
    ...
}
```

### 15. Modified: `agents/planner_agent.py`

Replace pandas query generation with SQL generation:

```python
prompt = f"""Given this SQLite schema, write 3 SQL queries to answer the analysis task.

Schema:
{formatted_schema}

Task: {task}

Return ONLY a JSON array of SQL query strings.
Each query must be a single SELECT statement.
Use proper SQLite syntax."""
```

### 16. Modified: `agents/executor_agent.py`

Use `DataHandler.run_sql()` instead of `DataHandler.load()` + `run_query()`:

```python
async def handle(event: Event) -> None:
    data_source = payload.get("data_source", "")  # SQLite path
    sql = payload.get("query", "")

    result = _handler.run_sql(data_source, sql)
    ...
```

### 17. Modified: `api/routes/manager.py`

Register the upload route. Optionally add `sqlite_db_path` to session creation response.

### 18. Modified: `config.py`

Add upload-related settings:

```python
max_upload_size_mb: int = 50
csv_data_dir: str = "/data/sessions"
```

### 19. Modified: `docker-compose.yml`

Mount a volume for SQLite data:

```yaml
backend:
  volumes:
    - csv_data:/data/sessions

volumes:
  csv_data:
```

---

## API Endpoints Summary

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/manager/sessions/{id}/upload` | Upload 1+ CSV files, validate, import to SQLite. Sets `pending_column_clarification=true` |
| `GET` | `/manager/sessions/{id}/data` | List tables in session's SQLite database |
| `GET` | `/manager/sessions/{id}/data/{table}` | Preview first 50 rows of a table |

## LangGraph Node Summary (New & Modified Nodes)

| Node | Type | Purpose |
|------|------|---------|
| `resolve_all_lines` | MODIFIED (CSV branch) | CSV: reads table name from SQLite file, sets `slots.line.canonical` + `resolved=True`. PG: unchanged. |
| `column_clarify` | NEW (interrupt) | LLM generates column meanings from names + 5 data rows → dedicated view → user edits → "All set" |
| `confirm_col_defs` | NEW | Locks column definitions into state, clears `pending_column_clarification` flag |
| `route_after_resolve_all_lines` | MODIFIED | Checks `pending_column_clarification`: true → `column_clarify`, false → `sync_session_context` |
| `sync_session_context` | MODIFIED | CSV: reads locked `column_definitions` from state. PG: reads from `global_registry`. |
| `show_suggested_aims` | MODIFIED | CSV branch: LLM generates suggestions from `column_definitions`. PG: reads from registry. |
| `send_to_planner` | MODIFIED | Payload uses `source_type: "sqlite"` with file path + table name |

## New Functions Summary

| Function | File | Purpose |
|----------|------|---------|
| `update_session_state()` | `session_db.py` | REST upload endpoint writes `source_type`, `sqlite_db_path`, `pending_column_clarification` to session state |
| `fetch_sqlite_schema()` | `sqlite_db.py` | Reads table/column info from SQLite file via PRAGMA |
| `csv_validator.validate()` | `csv_validator.py` | Full pre-check pipeline |
| `csv_to_sqlite.import()` | `csv_to_sqlite.py` | Validated CSV → SQLite tables |
| `data_handler.run_sql()` | `data_handler.py` | Executes SELECT against SQLite, returns results |
| `column_clarify()` | `nodes/column_clarify.py` | LLM generates column meanings from names + sample rows |
| `confirm_column_definitions()` | `nodes/column_clarify.py` | Locks definitions into state |

---

## File Structure Summary

```
backend/
├── api/
│   └── routes/
│       ├── manager.py              # + upload route
│       └── upload.py               # NEW — POST /sessions/{id}/upload
├── data/
│   ├── data_handler.py             # + run_sql() method
│   ├── csv_validator.py            # NEW — pre-check pipeline (13 checks)
│   └── csv_to_sqlite.py            # NEW — validated CSV → SQLite import
├── agents/
│   ├── manager/
│   │   ├── state.py                # + source_type, sqlite_db_path, column_definitions, pending_*
│   │   ├── session_db.py           # + update_session_state() for upload endpoint
│   │   ├── sqlite_db.py            # NEW — fetch_sqlite_schema() via PRAGMA
│   │   ├── db.py                   # unchanged (PG registry fallback)
│   │   ├── registry_context.py     # modified — CSV fetch_fn when column_definitions in state
│   │   └── nodes/
│   │       ├── multi_line.py       # modified — CSV branch in resolve_all_lines
│   │       ├── column_clarify.py   # NEW — LLM column meaning generation + confirm
│   │       ├── plan.py             # modified — payload includes sqlite path
│   │       ├── __init__.py         # modified — export new nodes
│   │       └── ...
│   ├── planner_agent.py            # SQL generator instead of pandas
│   └── executor_agent.py           # run_sql() instead of load()+run_query()
├── graph.py                        # + column_clarify + confirm_col_defs nodes + edges
├── routing.py                      # modified — route to column_clarify when pending
├── config.py                       # + max_upload_size_mb, csv_data_dir
└── docker-compose.yml              # + csv_data volume mount
```

---

## Graph Flow Comparison

### Current PG Flow

```
inject_time → extract_slots → merge_slots
    → resolve_all_lines (queries global_registry)
    → sync_session_context → resolve_time_filters → ask_missing
    → propose_or_refine_plans → merge_proposals → build_plan_message
    → detect_confirm → save_task_definition → send_to_planner
```

### New SQLite Flow (with column clarification)

```
UPLOAD (REST): upload → pre-checks → SQLite import → CALL update_session_state()
                                                      Sets: source_type = "csv"
                                                            sqlite_db_path = ...
                                                            pending_column_clarification = true
                                                                        │
CHAT START: inject_time → extract_slots → merge_slots
      │
      └── resolve_all_lines  (both PG and CSV go here — same node, different internal logic)
              │
              ├── source_type == "pg"  → queries global_registry, sets slots.line
              │
              └── source_type == "csv" → reads table name from SQLite file
                                          sets slots.line = {canonical: table_name, resolved: true}
              │
              └── router checks pending_column_clarification
                      │
                  ┌───┴───┐
                  │       │
                true     false
                  │       │
                  ▼       ▼
          column_clarify   sync_session_context
          (dedicated view)  (reads column_definitions from state)
                  │
          LLM generates meanings
          from column names + 5 data rows
                  │
          User edits → clicks "All set"
                  │
          confirm_col_defs
          (locks column_definitions, clears pending flag)
                  │
          sync_session_context  ← runs ONCE with locked defs
          (reads locked column_definitions from state)
                  │
          show_suggested_aims
          (CSV branch: LLM generates from column_definitions)
                  │
          resolve_time_filters → ask_missing
                  │
          propose_or_refine_plans
                  │
          merge_proposals → build_plan_message
                  │
          detect_confirm → save_task_definition
                  │
          send_to_planner
          (source_type: "sqlite", path in payload)
```

### Key Routing Differences

| Decision Point | PG Mode | CSV Mode |
|----------------|---------|----------|
| After `merge_slots` | → `resolve_all_lines` | → `resolve_all_lines` (same node, internal branch) |
| `resolve_all_lines` | Queries `global_registry` for line name | Reads table name from SQLite file, sets `slots.line` directly |
| After `resolve_all_lines` | → `sync_session_context` | → `column_clarify` (if pending) OR `sync_session_context` |
| `column_clarify` | Not applicable | LLM generates meanings from column names + 5 sample rows; user confirms in dedicated view |
| `sync_session_context` | Reads datasets from `global_registry` | Reads locked `column_definitions` from state |
| `show_suggested_aims` | Reads `suggested_aims` from registry | CSV branch: LLM generates from `column_definitions` |
| `send_to_planner` source_config | `{"url": "...", "table": "..."}` | `{"path": "/data/sessions/{id}/data.db", "table": "..."}` |

---

## Migration Path

1. **Phase 1** — Build upload endpoint + CSV pre-checks + SQLite import (`api/routes/upload.py`, `data/csv_validator.py`, `data/csv_to_sqlite.py`)
2. **Phase 2** — Build `column_clarify` node + `confirm_col_defs` node + graph wiring + routing
3. **Phase 3** — Build `fetch_sqlite_schema()` and wire into `sync_session_context` (with PG fallback)
4. **Phase 4** — Rewrite planner to generate SQL, executor to run `run_sql()`
5. **Phase 5** — E2E integration test: upload → validate → import → column clarify → confirm → suggestions → plan → SQL → results
6. **Phase 6** — Cleanup: keep PG path as fallback, remove when stable

---

## Design Review — Issues & Resolutions

The following issues were identified during planning and resolved:

| # | Issue | Severity | Resolution |
|---|-------|----------|------------|
| 1 | **SQL injection from LLM-generated SQL** — executor runs raw SQL from LLM. Could generate DROP/DELETE/UPDATE | Deferred | Guardrails phase (not now). During implementation, open SQLite in read-only mode (`?mode=ro`) and use a SELECT-only regex validator as a basic safety net. Full SQL injection guardrails will be added later. |
| 2 | **REST upload ↔ Graph timing gap** — upload is a REST endpoint, but column clarification is a graph node. Two round trips needed before analysis starts | **Resolved** | Column clarification opens a **dedicated full-screen view** (not inline chat). Upload returns → user sees normal chat → first message triggers graph → clarify view opens → user edits → "All set" → view closes → back to chat. The clarify step does NOT consume the user's message — it's a UI overlay. |
| 3 | **`resolve_all_lines` routing** — graph is hardcoded to go through this node, but CSV mode has no line to resolve | **Resolved** | Added `source_type: "pg" | "csv"` marker in state. `route_after_merge` checks it: "csv" → skip `resolve_all_lines`, go directly to `sync_session_context`. |
| 4 | **Frontend editable table capability** — inline editing in chat is not feasible with text-only messages | **Resolved** | Dedicated view handles this. Frontend renders an editable table component when `phase == "clarify_columns"`. On "All set", sends structured data back. |
| 5 | **LLM guessing column meanings from names alone** — names like `prod_cd` are ambiguous | **Resolved** | LLM prompt includes **first 5 data rows** alongside column names. Example: `prod_cd: {P100, P200, P101, P300, P205}` → LLM infers it's a product code, not a price. |
| 6 | **Multi-upload re-clarification** — if user uploads CSV1 (clarified), then CSV2 (needs clarification), should it re-trigger for just CSV2? | **Resolved** | **All tables shown together** in a single pass. When multiple CSVs are uploaded at once, the dedicated view shows sections for every table. User edits and confirms all at once with one "All set" click. No one-by-one flow. |
| 7 | **State serialization size** — column definitions with meanings bloat session state JSON | Low | Acceptable. JSONB handles it. Mitigation: store column_definitions as a separate JSON file alongside the SQLite file if it becomes a problem. |
| 8 | **Upload endpoint can't write to graph state** — upload is REST, but `source_type`, `sqlite_db_path`, `pending_column_clarification` need to be in `ManagerState` (PG state_json) before the graph runs. No existing function supports partial state updates from outside the graph. | **High** | Added `update_session_state(user_id, session_id, updates)` in `session_db.py`. Upload endpoint calls it after SQLite import to set `source_type="csv"`, `sqlite_db_path=...`, `pending_column_clarification=True`. |
| 9 | **Column clarification before sync_session_context (order dependency)** — original plan had `sync_session_context` run BEFORE column clarification (defs not locked yet), then AGAIN after (redundant). Also `resolve_all_lines` was skipped entirely, breaking `slots.line` resolution. | **High** | Reordered to: `resolve_all_lines` (CSV branch sets line) → `column_clarify` (generates meanings) → `confirm_col_defs` (locks) → `sync_session_context` (runs ONCE with locked defs). `resolve_all_lines` CSV branch reads table name from SQLite file directly. |

### Remaining Questions (not blocking)

- What happens to the SQLite file when a session is deleted? (auto-cleanup needed)
- Should the column clarification step allow the user to skip entirely if they trust the LLM?
- SQL injection guardrails — planned for later phase, not v1

---


