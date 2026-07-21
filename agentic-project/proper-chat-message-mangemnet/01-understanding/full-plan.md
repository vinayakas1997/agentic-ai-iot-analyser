# Full Plan — Tagged Context Enrichment for Chat

---

## 1. Data Model

### `state_json` — Full Schema

```json
{
  "enrichment_mode": "research",
  "turns": [
    {
      "user": "Analyze melon trends by season",
      "agent": "**Analyze melon trends** — results shown below.",
      "created_at": "turn-uuid-1",
      "result_uuid": "result-uuid-1",
      "aims": ["Analyze melon trends"],
      "datasets": ["melons", "fruit_quality"],
      "analysis_actions": [...]
    }
  ],
  "chat_query_results": {
    "result-uuid-1": {
      "sql": "SELECT season, AVG(yield) FROM melons GROUP BY season",
      "columns": ["season", "avg_yield"],
      "rows": [{"season":"summer","avg_yield":1420}, ...],
      "row_count": 4,
      "chart_suggestions": { ... }
    }
  },
  "completed_actions": {
    "Analyze melon trends": "turn-uuid-1"
  },
  "context_summaries": {
    "aim:Analyze melon trends": [
      {
        "turn_timestamps": ["turn-uuid-1", "turn-uuid-2", "turn-uuid-3", "turn-uuid-4", "turn-uuid-5"],
        "summary": "User analyzed melon yield by season. Summer avg=1420, fall avg=980. Bar chart used.",
        "created_at": "2026-07-21T12:00:00Z"
      }
    ],
    "dataset:melons": [
      {
        "turn_timestamps": ["turn-uuid-1", "turn-uuid-3", "turn-uuid-5", "turn-uuid-7", "turn-uuid-9"],
        "summary": "5 melon analyses covering yield, pricing, seasonal trends.",
        "created_at": "2026-07-21T12:30:00Z"
      }
    ]
  },
  "selected_aims": [...],
  "attached_datasets": [...],
  "output_results": [...]
}
```

### Key differences from current model

| Current | New | Rationale |
|---|---|---|
| Turn has no `aims`/`datasets` | Every turn has `aims: string[]`, `datasets: string[]` | Enables per-tag filtering for enrichment |
| `chat_query_results` keyed by timestamp string | Keyed by UUID | Prevents key collision |
| No `context_summaries` | `context_summaries: { tag: [summary, ...] }` | Stores compressed turn-group summaries |
| `completed_actions` maps name → timestamp | Maps name → turn timestamp | Preserves scroll-to-turn functionality |
| No `result_uuid` on turn | Turn has `result_uuid` field | Per-run result attribution (not last-write-wins) |
| No enrichment mode | `enrichment_mode: "research" | "summary"` | Controls enrichment strategy |
| No version locking | Uses `ManagerSession.version` column | Prevents concurrent-write data loss |

### Turn type definition update

The `Turn` interface in `types/manager.ts:72-83` must be updated to include the new fields:

```typescript
export interface Turn {
  turn_index?: number;
  user: string;
  agent: string;
  ui: TurnUi | null;
  schema: SchemaSnapshot | null;
  created_at?: string;
  result_uuid?: string;                      // NEW: links to specific result in chat_query_results
  aims?: string[];                           // NEW: list of aim names this turn relates to
  datasets?: string[];                       // NEW: list of dataset names this turn relates to
  description?: string | null;
  benefits?: string | null;
  columns?: { dataset: string; name: string }[] | null;
  analysis_actions?: AnalysisAction[];
}
```

---

## 2. Turn Lifecycle

### 2a. Chat messages (`/api/v2/messages`)

**Frontend → Backend request**:
```json
{
  "session_id": "...",
  "message": "why were melons higher in summer?",
  "line_name": "melons,fruit_quality",
  "attached_aims": ["Analyze melon trends"],
  "enrichment_mode": "research",
  "history": []
}
```
Note: `history` is always sent as empty `[]` — enrichment replaces it. If non-empty, backend ignores it and logs a warning (graceful fallback for stale clients).

**Backend processing** (`api.py` `send_message`):

1. Read `state_json` from DB.
2. **Guard check**: if `enrichment_mode == "research"` AND no `attached_aims` AND no `dataset_names` from `line_name`, return early: `"Please attach a dataset or aim, or switch to SUMMARY mode."` — no LLM call.
3. Determine enrichment strategy based on `enrichment_mode`:
   - **RESEARCH**: filter `turns` where `aims ∩ attached_aims ≠ ∅` OR `datasets ∩ line_name ≠ ∅`.
   - **SUMMARY**: select ALL turns.
4. Build enrichment block (see §4a):
   - For each matching tag, load all summaries from `context_summaries[tag]`.
   - Load raw turns not yet covered by any summary (last 5 per matching tag).
   - Deduplicate by checking ALL turn timestamps (not just first).
   - For each turn with a `result_uuid`, pull its specific result from `chat_query_results`. Fall back to `created_at` lookup for old sessions.
   - Cap total enrichment at 4000 tokens. Stop adding when limit reached.
5. Call LLM with enrichment block + message + dataset schemas.
6. Save response turn with tags: `{ aims: attached_aims, datasets: dataset_names_from_line_name }`.
7. Use optimistic locking: read `ManagerSession.version`, write only if version matches, increment version.
8. Return response.

**New MessageRequest** (`api.py`):
```python
class MessageRequest(BaseModel):
    session_id: str
    message: str
    line_name: str = ""
    attached_aims: list[str] = []
    enrichment_mode: str = "research"  # "research" | "summary"
    history: list[dict] | None = None  # kept for backward compat, ignored when enrichment_mode is set
```

### 2b. AimBar RUN — unified handler (`ChatSection.tsx` `handleRunAimSql`)

`handleRunAimSql` is the **single entry point** for running any aim (normal aims AND analysis actions). This eliminates the SQL generation mismatch that would occur with separate handlers.

**Flow:**
1. Turn created client-side with `aims: [aimDef.aim]`, `datasets: aimDef.datasets`, and `result_uuid: crypto.randomUUID()`.
2. Calls `/api/v2/execute-query` (no enrichment needed — it's a direct SQL query).
3. On success, persists turn via `persistTurns()` with fields included.
4. Result stored in `chatQueryResults` (UUID key).
5. Stores in `completedActions` as `{ [aimDef.aim]: turnId }` (maps name → turn timestamp for scroll-to-turn).

**SQL generation:** Uses `aimDef.description` in the SQL prompt (line 230-245). Both normal aims and analysis actions carry descriptions, so the same code path works for both.

**Why not two handlers?** `handleRunAnalysis` had identical SQL generation logic to `handleRunAimSql`. The only difference was `completedActions` update. By adding that to `handleRunAimSql`, we eliminate redundancy and the risk of divergent SQL generation.

### 2c. Analysis action — two-step flow (TurnBubble toggle + AimBar RUN)

Analysis actions are now two-step: **attach first, then run**. This prevents auto-execution and gives the user control over enrichment scope.

**Step 1: TurnBubble toggle** (user clicks "Add for analysis"):
- Action is added to `selectedAims` as `{ aim: action.name, description: action.description, datasets: action.datasets }`.
- Action's datasets are attached via `storeAddMultiple` / `storeAttachMultiple`.
- NO execution happens. The action is only staged in the composer.

**Step 2: AimBar RUN** (user clicks "Run" on the AimBar):
- Calls `handleRunAimSql` with the aim definition.
- `handleRunAimSql` already handles descriptions in SQL generation (line 230-245).
- Turn created with `aims: [action.name]`, `datasets: action.datasets`, `result_uuid: crypto.randomUUID()`.
- Result stored in `chatQueryResults` (UUID key).
- `completedActions` updated: `{ [action.name]: turnId }`.

**TurnBubble toggle states:**

| State | Button | Click Action |
|---|---|---|
| Not attached | "Add for analysis" | Attaches aim + datasets to composer |
| Attached | "Added for analysis" (teal) | Detaches aim + unneeded datasets |
| Completed + attached | "Added ✓" (green) | Detaches aim |
| Completed + detached | "View" (scroll to result) | Just scrolls (no attach) |

### 2d. Re-run mechanism

Completed aims can be re-run from two locations:

**From completed actions bar:**
Each chip shows a small replay icon (↻) next to the scroll button. Clicking:
1. Re-adds the aim to `selectedAims` (if not already there)
2. Attaches its datasets
3. Calls `handleRunAimSql` to generate new SQL and execute
4. The old result remains in `chatQueryResults` (new result gets its own UUID)

**From OutputPanel result card:**
Add a "Re-run" button alongside "Show Details". Same behavior as above.

**Implementation:**
```typescript
const handleRerunAim = async (aimDef: { aim: string; description?: string; datasets?: string[] }) => {
  // Re-add to selectedAims if needed
  if (!selectedAims.find(a => a.aim === aimDef.aim)) {
    useAim(aimDef);
  }
  // Run via the unified handler
  await handleRunAimSql(aimDef);
};
```

**Edge case: re-run same aim 3 times**
Each run creates a new turn with its own `result_uuid`. `completedActions` updates to point to the latest turn. All 3 results remain in `chatQueryResults`. Enrichment includes all 3 turns (each with its own result via per-turn `result_uuid`).

### 2e. Tag persistence

**`persistTurns()`** (`ChatSection.tsx`) — field naming matches existing backend format (`timestamp` for backward compat with persisted sessions):
```typescript
const currentTurns = sState.turns.map((t) => ({
  user: t.user,
  agent: t.agent || "",
  timestamp: t.created_at || crypto.randomUUID(),  // stored as "timestamp" — backend reads this name
  result_uuid: t.result_uuid,
  aims: t.aims || [],
  datasets: t.datasets || [],
  analysis_actions: t.analysis_actions,
}));
```

### 2f. Tag restoration

**`bootstrap()` / `switchSession()`** (`sessionStore.ts`) — reads `t.timestamp` for backward compat with existing persisted sessions (which store the field as `"timestamp"`, not `"created_at"`):
```typescript
const loadedTurns = (detail.turns || []).map((t: any) => ({
  ...
  created_at: t.created_at || t.timestamp || new Date().toISOString(),
  result_uuid: t.result_uuid,
  aims: t.aims || [],
  datasets: t.datasets || [],
  analysis_actions: t.analysis_actions || undefined,
}));
```

---

## 3. Summary Pipeline

### 3a. Trigger condition (idempotent + debounced)

Frontend tracks turn count. Trigger strategy depends on enrichment mode:

**RESEARCH mode:** Count turns per tag. When any tag reaches a multiple of 5 AND those turns aren't already covered by an existing summary, a summary is triggered.

**SUMMARY mode:** Count ALL turns (not per-tag). When total turns reach a multiple of 5, trigger a single global summary covering all recent turns. This handles untagged turns that have no aim/dataset tags.

Debounced at 2s to prevent rapid-fire on batch sends.

Implementation in `ChatSection.tsx`:
```typescript
const summaryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

useEffect(() => {
  if (summaryTimerRef.current) clearTimeout(summaryTimerRef.current);

  if (enrichmentMode === "summary") {
    // SUMMARY mode: count all turns, trigger global summary
    const allTimestamps = turns.map(t => t.created_at).filter(Boolean) as string[];
    if (allTimestamps.length > 0 && allTimestamps.length % 5 === 0) {
      const tag = "__all__"; // special key for global summary
      const existingSummaries = contextSummaries[tag] || [];
      const alreadyCovered = existingSummaries.some(s =>
        allTimestamps.every(ts => s.turn_timestamps.includes(ts))
      );
      if (!alreadyCovered) {
        const group = allTimestamps.slice(-5);
        summaryTimerRef.current = setTimeout(() => triggerSummary(tag, group), 2000);
      }
    }
  } else {
    // RESEARCH mode: count per tag
    const tagTurnCount: Record<string, string[]> = {};
    for (const t of turns) {
      for (const aim of (t.aims || [])) {
        const tag = `aim:${aim}`;
        if (!tagTurnCount[tag]) tagTurnCount[tag] = [];
        tagTurnCount[tag].push(t.created_at);
      }
      for (const ds of (t.datasets || [])) {
        const tag = `dataset:${ds}`;
        if (!tagTurnCount[tag]) tagTurnCount[tag] = [];
        tagTurnCount[tag].push(t.created_at);
      }
    }

    for (const [tag, timestamps] of Object.entries(tagTurnCount)) {
      if (timestamps.length > 0 && timestamps.length % 5 === 0 && !summarizingTags.has(tag)) {
        const existingSummaries = contextSummaries[tag] || [];
        const alreadyCovered = existingSummaries.some(s =>
          timestamps.every(ts => s.turn_timestamps.includes(ts))
        );
        if (alreadyCovered) continue;

        const group = timestamps.slice(-5);
        summaryTimerRef.current = setTimeout(() => triggerSummary(tag, group), 2000);
      }
    }
  }
}, [turns, enrichmentMode]);
```

### 3b. Summary generation

**Frontend**:
1. Sets `summarizingTags` state to show "Summarizing..." UI.
2. Collects the 5 turn UUIDs for that tag.
3. Calls `POST /api/v2/sessions/{sessionId}/summarize-context`.

**Backend** (`api.py` new endpoint):
```python
class SummarizeContextRequest(BaseModel):
    tag: str  # e.g. "aim:Analyze melon trends"
    turn_timestamps: list[str]

class SummarizeContextResponse(BaseModel):
    tag: str
    summary: str
    created_at: str
```

Processing:
1. Read `state_json` from DB using optimistic locking (read version).
2. **Idempotency check**: if `state_json.context_summaries[tag]` already has an entry covering all `turn_timestamps`, return it immediately (no LLM call).
3. Fetch turns by `turn_timestamps`.
4. Build prompt: "Summarize the following conversation thread in 2-3 sentences:\n\n{turns_text}".
5. Call LLM for compact summary.
6. Append to `state_json.context_summaries[tag]`.
7. Save with version check/increment.
8. Return.

**Frontend**:
1. On response, hide "Summarizing..." UI.
2. Update local `contextSummaries` state.
3. On timeout (5s), hide "Summarizing..." and continue without summary.

### 3c. Summary storage structure

```json
"context_summaries": {
  "aim:Analyze melon trends": [
    {
      "turn_timestamps": ["uuid-1", "uuid-2", "uuid-3", "uuid-4", "uuid-5"],
      "summary": "User analyzed melon yield by season. Summer avg=1420, fall avg=980.",
      "created_at": "2026-07-21T12:00:00Z"
    }
  ]
}
```

Each tag gets an array of summaries, each covering exactly 5 turns. The array grows over time as the thread deepens. At most 5 raw turns per tag are ever sent in enrichment (the latest ones not yet covered by a summary).

---

## 4. Enrichment Pipeline

### 4a. Enrichment block builder (backend helper function)

```python
import re

def build_enrichment_block(
    state: dict,
    attached_aims: list[str],
    attached_datasets: list[str],
    mode: str,
    max_tokens: int = 4000
) -> str:
    blocks = []
    seen_timestamps = set()
    total_tokens = 0

    if mode == "research":
        if not attached_aims and not attached_datasets:
            return ""  # caller will return early with user-facing message
        tags = (
            [f"aim:{a}" for a in attached_aims] +
            [f"dataset:{d}" for d in attached_datasets]
        )
    elif mode == "summary":
        tags = list(state.get("context_summaries", {}).keys())
    else:
        return ""

    summaries = state.get("context_summaries", {})
    turns = state.get("turns", [])
    chat_results = state.get("chat_query_results", {})

    for tag in tags:
        tag_summaries = summaries.get(tag, [])
        covered_ts = set()
        for s in tag_summaries:
            covered_ts.update(s["turn_timestamps"])
            # Dedup check: only skip if ALL turns are already covered
            if all(ts in seen_timestamps for ts in s["turn_timestamps"]):
                continue
            text = f"[Summary: {tag}] {s['summary']}"
            tokens = estimate_tokens(text)
            if total_tokens + tokens > max_tokens:
                break
            blocks.append(text)
            total_tokens += tokens
            seen_timestamps.update(s["turn_timestamps"])

        tag_name = tag.split(":", 1)[1]
        relevant_turns = [
            t for t in turns
            if tag_name in (t.get("aims") or []) or tag_name in (t.get("datasets") or [])
        ]
        uncovered = [t for t in relevant_turns if t["created_at"] not in covered_ts]

        for t in uncovered[-5:]:  # last 5 uncovered turns
            if t["created_at"] in seen_timestamps:
                continue
            result_text = ""
            # New format: per-turn result_uuid
            result_uuid = t.get("result_uuid")
            if result_uuid:
                r = chat_results.get(result_uuid, {})
                if r:
                    sql = r.get("sql", "")
                    sql_display = sql[:80] + " ... [truncated]" if len(sql) > 80 else sql
                    result_text = f" | SQL: {sql_display} | Rows: {r.get('row_count', 0)}"
            else:
                # Old format: try backward-compat lookup by created_at timestamp
                r = chat_results.get(t["created_at"], {})
                if r:
                    sql = r.get("sql", "")
                    sql_display = sql[:80] + " ... [truncated]" if len(sql) > 80 else sql
                    result_text = f" | SQL: {sql_display} | Rows: {r.get('row_count', 0)}"

            text = f"[Turn] User: {t['user'][:80]} | Agent: {t['agent'][:80]}{result_text}"
            tokens = estimate_tokens(text)
            if total_tokens + tokens > max_tokens:
                break
            blocks.append(text)
            total_tokens += tokens
            seen_timestamps.add(t["created_at"])

    return "\n".join(blocks)


def estimate_tokens(text: str) -> int:
    """Rough token estimation: ~4 chars per token."""
    return len(text) // 4 + 1
```

### 4b. Enrichment block format (what the LLM sees)

```
--- Context for "Analyze melon trends" ---
[Summary] User analyzed melon yield by season. Summer avg=1420, fall avg=980.
[Summary] Extended with pricing. Correlation between yield and price: r=0.65.
[Turn] User: "add temperature data" | Agent: SQL: SELECT ... | Rows: 120 | Chart: scatter

--- Context for dataset "melons" ---
[Summary] 5 melon analyses covering yield, pricing, seasonal trends.
[Turn] User: "compare to last year" | Agent: SQL: SELECT ... | Rows: 48 | Chart: line

User's question: why were melons higher in summer?
```

### 4c. LLM prompt structure (must be designed before implementation)

**System prompt**:
```
You are a data analysis assistant. Current mode: {enrichment_mode}.

INTERPRET THE CONTEXT:
The context below shows previous analysis work in this session. Each section is labeled with the
aim or dataset it relates to. "[Summary]" entries are compressed history of multiple turns.
"[Turn]" entries are individual interactions with their SQL and row counts.

HOW TO RESPOND:
- RESEARCH mode: Use the context to answer questions and generate new SQL queries to explore further.
  You can propose new aims and analysis actions.
- SUMMARY mode: Recap and summarize findings from the context. Do NOT generate new SQL queries
  or propose new analysis actions.

IMPORTANT: The context is filtered — it only shows what's relevant to your current attached aims
and datasets. If you need information about something not shown, the user needs to attach it first.
```

**User message**:
```
{enrichment_block}

Dataset schemas:
- melons: columns [season, yield, price, region]

User: why were melons higher in summer?
```

---

## 5. Mode Management

### 5a. Field name

The mode is stored in `state_json` as `enrichment_mode` (NOT `mode` — that name is already used by the `ManagerSession.mode` DB column).

```python
# state_json
{
  "enrichment_mode": "research",  # "research" | "summary"
  ...
}
```

### 5b. Frontend toggle

A toggle button in the composer area or navbar. Options: RESEARCH | SUMMARY.

**Behavior per mode**:

| Aspect | RESEARCH | SUMMARY |
|---|---|---|
| Compose area | Shows attach-aims/datasets UI | Hides attach UI |
| Send message | Requires `line_name` or `attached_aims` | No requirements |
| Analysis action buttons (TurnBubble) | Available | Hidden or disabled |
| Aim proposals | Generated | Not generated |
| LLM behavior | Generate SQL, explore data | Recap findings, answer questions |

### 5c. Mode persistence

Stored in `state_json.enrichment_mode`. Persisted via `persistTurns` or a dedicated PATCH. Restored in `bootstrap()` / `switchSession()`. Default for existing sessions: `"research"`.

### 5d. Cleanup on new session

`newSession()` in `sessionStore.ts` must also clear:
- `aimProposals: []` (currently NOT cleared — stale proposals leak from previous session)
- `context_summaries: {}` (new field, must be empty for fresh session)
- `enrichment_mode: "research"` (reset to default)

---

## 6. ChatQueryResults Key Change & Completed Actions

### Current
```typescript
const now = new Date().toISOString();
chatQueryResults: { ...s.chatQueryResults, [now]: resultState },
completedActions: { ...s.completedActions, [action.name]: now },
```

### New
```typescript
const turnId = crypto.randomUUID();
const resultId = crypto.randomUUID();

chatQueryResults: { ...s.chatQueryResults, [resultId]: resultState },
completedActions: { ...s.completedActions, [action.name]: turnId },
```

This way:
- `turns[].created_at` = UUID (never collides)
- `turns[].result_uuid` = UUID → lookup in `chatQueryResults` (per-turn, not last-write-wins)
- `completedActions[aim_name]` = turn UUID → scroll-to-turn (not result lookup)
- Old sessions use backward-compat: if `result_uuid` is absent, fall back to `created_at` key in `chatQueryResults`

---

## 7. Optimistic Locking (NEW — critical for correctness)

### Problem

`send_message` (via `/messages`) and `/summarize-context` both read `state_json`, modify it, and write it back. Without locking, two concurrent requests can overwrite each other's changes.

### Solution

Use the existing `ManagerSession.version` column (currently unused):

```python
# In send_message and summarize-context:
async with AsyncSessionLocal() as db:
    row = await db.execute(
        select(ManagerSession).where(
            ManagerSession.session_id == session_id,
            ManagerSession.version == expected_version_from_state
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=409, detail="Concurrent modification. Retry.")

    # ... modify state ...

    row.state_json = updated_state
    row.version += 1
    await db.commit()
```

**Frontend**: The frontend should retry `persistTurns` and `/summarize-context` calls on 409 response with exponential backoff.

---

## 8. File Changes Summary

### Frontend

| File | Change |
|---|---|
| `types/manager.ts` | Add `aims?: string[]`, `datasets?: string[]`, `result_uuid?: string` fields to `Turn` interface |
| `ChatSection.tsx` | Add `attached_aims` to `handleSend` payload; tag turns (`aims`, `datasets`, `result_uuid`) in `handleRunAimSql`; add `completedActions` update in `handleRunAimSql` (unified handler — `handleRunAnalysis` removed); add `handleRerunAim` function; add idempotent + debounced summary trigger logic (mode-aware: per-tag for RESEARCH, global for SUMMARY); add "Summarizing..." UI; send `enrichment_mode` in payload; update `completedActions` to store turn timestamp (not result UUID) |
| `sessionStore.ts` | Restore `aims`, `datasets`, `result_uuid`, `context_summaries` in `bootstrap`/`switchSession`; add `enrichment_mode` field (default `"research"`); reset `aimProposals`, `context_summaries`, `enrichment_mode` in `newSession` |
| `datasetStore.ts` | Keep as-is (already has `clear()`) |
| `api/client.ts` | Add `summarizeContext()` function; update `sendMessage` type to include `attached_aims` and `enrichment_mode`; add retry logic for 409 responses |
| `TurnBubble.tsx` | Add "Add for analysis" / "Added for analysis" toggle on each action pill; add concurrency feedback (disable + tooltip when another action is running); remove direct `onRunAnalysis` callback (replaced by toggle → AimBar run flow) |
| `OutputPanel.tsx` | Add "Add for analysis" / "Added for analysis" toggle on each result card; add "Re-run" button on result cards; add expandable context view showing tag-filtered history |
| `Navbar.tsx` / `ContextSection.tsx` | Add `enrichment_mode` toggle UI (RESEARCH / SUMMARY); show current mode; add remove button (×) on completed action chips for full cleanup |

### Backend

| File | Change |
|---|---|
| `api.py` | `MessageRequest`: add `attached_aims`, rename `mode` to `enrichment_mode`; `send_message`: add guard for RESEARCH + no attachments, use enrichment block instead of history, tag turns on save, use optimistic locking; new `POST /sessions/{id}/summarize-context` endpoint with idempotency; new `build_enrichment_block()` helper with token cap, proper dedup, backward-compat key lookup |
| `llm_client.py` (or equivalent) | Accept enrichment block format; implement mode-specific system prompts (research vs summary) with clear instructions for interpreting `[Summary]` and `[Turn]` entries |
| `db/models.py` | No structural changes needed — `state_json` remains a JSON blob; `version` column already exists |

---

## 9. Rollout / Migration

### Phase 1: Foundation
- Update `Turn` type in `types/manager.ts` — add `aims`, `datasets`, `result_uuid` fields.
- Update `chatQueryResults` key from timestamp to UUID.
- Add `aims`, `datasets`, `result_uuid` fields to turns in persistence/restore (field persisted as `"timestamp"` for backward compat).
- Add `context_summaries` field to state (initially empty).
- Add `enrichment_mode` field to state (default: `"research"`).
- Implement optimistic locking with `version` column.
- **Backward-compat**: `build_enrichment_block` falls back to `created_at` key if `result_uuid` absent.
- **`newSession()` cleanup**: add `aimProposals: []`, `context_summaries: {}`, `enrichment_mode: "research"` to the state reset.
- **Unify run path**: add `completedActions` update to `handleRunAimSql`; remove `handleRunAnalysis` (all aims now go through `handleRunAimSql`).

### Phase 2: Enrichment
- Implement `build_enrichment_block()` in backend with: token cap (4000), proper dedup (all timestamps), backward-compat key lookup, SQL truncation marker.
- Modify `send_message` to use enrichment instead of `history` (ignore `history` if `enrichment_mode` set).
- Add guard: RESEARCH + no attachments → early return (no LLM call).
- Add `attached_aims` and `enrichment_mode` to `MessageRequest`.
- Frontend sends `attached_aims`, `enrichment_mode`, and empty `history` with every message.

### Phase 3: Summarization
- Implement `POST /sessions/{id}/summarize-context` endpoint with idempotency check.
- Frontend summary trigger logic: idempotent (check existing coverage), debounced (2s), with "Summarizing..." UI and 5s timeout fallback.
- **Mode-aware trigger**: RESEARCH mode triggers per-tag (every 5 turns per tag); SUMMARY mode triggers globally (every 5 turns total, stored under `__all__` key).

### Phase 4: Mode management + attachment control
- `enrichment_mode` toggle UI in composer/navbar.
- Store mode on session.
- Adapt UI per mode (show/hide attach area, analysis buttons).
- **TurnBubble toggle**: "Add for analysis" / "Added for analysis" on action pills (two-step flow).
- **Re-run mechanism**: "Re-run" button on completed action chips and OutputPanel result cards.
- **Remove from completed actions**: × button on chips for full cleanup.

### Phase 5: Prompt engineering
- Design system prompts for both RESEARCH and SUMMARY modes.
- Must explain enrichment block format (`[Summary]`, `[Turn]`, tag labels).
- RESEARCH: generate SQL, proposals, actions.
- SUMMARY: recap only, no new queries.

---

## 10. Edge Cases

| Case | Behavior |
|---|---|
| RESEARCH mode + no attachments | Backend returns early: "Please attach a dataset or aim, or switch to SUMMARY mode." No LLM call. |
| SUMMARY mode + empty session | LLM response: "No analysis history yet. Switch to RESEARCH to start exploring." |
| Turn tagged with aim A, but user later detaches A | Turn stays tagged. EXCLUDED from enrichment unless A is re-attached. |
| Same turn tagged with aim A AND dataset X | Dedup checks ALL turn timestamps. Included once, not dropped. |
| Summary generation fails (LLM error) | "Summarizing..." state times out after 5s. Summary skipped — raw turns still available for enrichment. |
| Old sessions with no tags on turns | Untagged turns: skipped in RESEARCH mode enrichment; included in SUMMARY mode enrichment. Backward-compat key lookup in `chat_query_results`. |
| Session with 1000+ turns | Summaries cover turns in groups of 5. At most 5 raw turns per tag in enrichment. Token cap at 4000. |
| Same aim run 3 times | Each run has its own `result_uuid` on the turn. Enrichment uses per-turn result, not last-write-wins. |
| Summary trigger on reload | Idempotency check: only triggers if turn timestamps aren't already covered by an existing summary. |
| Two browser tabs | Both tabs can trigger summary for same turns. Backend's `/summarize-context` has idempotency check — returns existing summary instead of creating duplicate. Optimistic locking prevents concurrent-write data loss. |
| Stale client sends full `history` | Backend ignores `history` when `enrichment_mode` is set. Logs warning. No token waste. |
| SQL string >80 chars | Truncated with `"... [truncated]"` marker. No mid-clause cut. |
| Enrichment block exceeds 4000 tokens | Stops adding entries. LLM gets partial context but prioritizes summaries over raw turns. |
| **Re-running a completed aim** | Clicking "Re-run" on a completed action chip or OutputPanel card re-adds the aim to `selectedAims`, attaches datasets, and calls `handleRunAimSql`. Old result remains in `chatQueryResults`; new result gets its own UUID. |
| **Detaching aim from composer vs completedActions** | Detaching from AimBar removes from `selectedAims` (excludes from enrichment) but keeps in `completedActions` (scroll-back still works). Remove button (×) on chip does full cleanup (removes from both). |
| **Analysis action two-step: toggle without run** | User clicks "Add for analysis" on TurnBubble but doesn't click Run. Aim is staged in composer. No SQL executed. User can detach or run later. |
| **SUMMARY mode + untagged turns** | Summary trigger counts ALL turns (not per-tag). Global summary stored under `__all__` key. Enrichment includes all summaries in SUMMARY mode. |
| **Re-run same aim 3 times** | Each run creates a new turn with its own `result_uuid`. `completedActions` updates to point to latest turn. All 3 results remain in `chatQueryResults`. Enrichment includes all 3 turns (each with its own result). |

---

## 11. Success Criteria

1. LLM receives only relevant context (no raw history dump).
2. Follow-up questions about analysis results are answered correctly using enrichment.
3. Token cost per message is lower than current flat-history approach.
4. Summarization keeps context window bounded regardless of session length.
5. Mode toggle correctly switches enrichment strategy and LLM behavior.
6. Old sessions (pre-migration) degrade gracefully (no enrichment in RESEARCH, full data in SUMMARY, backward-compat key lookup).
7. No data loss from concurrent writes (optimistic locking passes).
8. No duplicate summaries on reload or multi-tab.
9. SQL truncation never cuts mid-clause without a marker.
10. RESEARCH mode with no attachments never calls the LLM (saves tokens).
11. Re-running a completed aim produces a new result without losing the old one.
12. Analysis actions are two-step: attach first, then run. No auto-execution.
13. SUMMARY mode summary trigger works for untagged turns (global summary).
14. Detaching an aim from the composer excludes it from enrichment but keeps scroll-back working.
