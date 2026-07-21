# AGENTIC-AI-IOT-ANALYSER — Implementation Tracker

> Auto-updated as each phase completes. Review this file after all phases are done.

## Phase Tracker

| Phase | Description | Status | Date |
|---|---|---|---|---|
| 1 | Foundation — types, state, locking, unified run path | ✅ DONE | 2026-07-21 |
| 2 | Enrichment — `build_enrichment_block`, guard, enrichment replace history | ✅ DONE | 2026-07-21 |
| 3 | Summarization — `/summarize-context` endpoint, trigger logic | ✅ DONE | 2026-07-21 |
| 4 | Mode Management — RESEARCH/SUMMARY toggle, UI adapt | ✅ DONE | 2026-07-21 |
| 5 | Prompt Engineering — `llm_client.py`, mode-specific prompts | ✅ DONE | 2026-07-21 |

## Open Issues

| # | Issue | Severity | Notes |
|---|---|---|---|
| 1 | ChartSuggestions type mismatch (`api/client.ts`) | Low | ✅ Fixed. Imported `ChartConfig` union type instead of inline `string`. |
| 2 | Zustand subscribe signature (`ChatSection.tsx`) | Low | ✅ Fixed. Switched to single-argument `.subscribe(listener)` with prev-state guard. |
| 3 | recharts `ratio`/`percent` props (`QueryActions.tsx:150,213`) | Low | ✅ Fixed. `ratio` → `aspectRatio`; added null fallback `percent ?? 0`. |
| 4 | LLM `refusal` field ignored (`aims.py`) | High | ✅ Fixed. Added `msg.refusal` fallback in `generate_chat_response`. |
| 5 | Double system message rejected by vLLM (`aims.py`) | High | ✅ Fixed. Combined system prompt + enrichment block into single message. |
| 6 | LLM refusal due to missing authorization in prompts (`aims.py`, `llm_client.py`) | Med | ✅ Fixed. Added explicit "AUTHORIZED to discuss data" to all prompts. |
| 7 | SUMMARY mode blocked by dataset guard (`api.py:556`, `aims.py:274`) | High | ✅ Fixed. Changed guard to only apply in RESEARCH mode. |
| 8 | `generate_aim` missing import/definition (`api.py:293`) | Low | Dead endpoint `POST /aim/new-research` — never called from frontend. Remove or implement. |

## Phase Details

### Phase 1: Foundation ✅ (2026-07-21)

**Goal:** Establish the data model, state management, and locking for the tagged context enrichment system.

**Plan source:** `agentic-project/proper-chat-message-mangemnet/01-understanding/full-plan.md`

**Files modified:**

| File | Changes |
|---|---|
| `frontend/src/types/manager.ts` | Added `result_uuid`, `aims`, `datasets` to `Turn` interface |
| `frontend/src/stores/sessionStore.ts` | Added `contextSummaries`, `enrichmentMode` state; updated `turnFromResponse()`; updated `bootstrap()`/`switchSession()` to restore new fields; fixed `newSession()` to clear `aimProposals`, `contextSummaries`, `enrichmentMode` |
| `frontend/src/sections/ChatSection.tsx` | Fixed `errorState` bug (was `RefenceError`); switched `chatQueryResults` from timestamps to UUID keys; added `result_uuid`, `aims`, `datasets` to turn creation; added `completedActions` update to `handleRunAimSql`; **removed `handleRunAnalysis`** (unified into `handleRunAimSql`); removed `runningAction` state; added `enrichmentMode` selector; added `handleToggleAction()` (two-step analysis action flow), `handleRerunAim()`, `handleRemoveCompletedAction()`; updated completed actions bar with re-run (↻) + remove (×) buttons; backward-compat result lookup (`t.result_uuid ?? t.created_at`) |
| `frontend/src/components/TurnBubble.tsx` | Replaced `onRunAnalysis` + `runningAction` with `onToggleAction`, `selectedAims`, `runningAim`, `onRerunAim`; 4 toggle states: Add / Added (teal) / Completed+Added (green) / View; re-run button on completed items |
| `backend/api.py` | Optimistic locking in `send_message`: captures `session.version` on read, checks version + returns 409 on mismatch, increments version on write |

**Key decisions:**
- `handleRunAimSql` is now the single entry point for all runs (normal aims + analysis actions). `handleRunAnalysis` removed because both had identical SQL generation logic.
- Analysis actions are two-step: TurnBubble toggle attaches to composer, AimBar "Run" executes.
- `chatQueryResults` keys are now UUIDs. Old sessions fall back to `created_at` key lookup.

### Phase 2: Enrichment ✅ (2026-07-21)

**Plan source:** `full-plan.md` §2a, §4a, §4b

**Files modified:**

| File | Changes |
|---|---|
| `backend/api.py` | Added `build_enrichment_block()` + `estimate_tokens()` helpers; updated `MessageRequest` with `attached_aims`, `enrichment_mode` fields; added guard (RESEARCH + no attachments → early return); enrichment block replaces `history` when `enrichment_mode` is set; saved turns tagged with `aims`, `datasets` |
| `backend/aims.py` | `generate_chat_response()` accepts optional `enrichment_block` parameter (injected as system-level context, replaces history path) |
| `frontend/src/api/client.ts` | Added `ApiError` class (status code), `withRetry()` wrapper (3 attempts, exponential backoff on 409); `sendMessage()` now accepts `attachedAims`, `enrichmentMode`, sends empty `history`; retry applied to `sendMessage`, `executeQuery`, `updateSessionState` |
| `frontend/src/stores/sessionStore.ts` | `sendUserMessage()` accepts `attachedAims`, `enrichmentMode` params; sends empty history; `turnFromResponse()` populates `aims`/`datasets` from passed params |
| `frontend/src/sections/ChatSection.tsx` | `handleSend()` passes `selectedAims` + `enrichmentMode` to `sendUserMessage`; `persistTurns()` saves `enrichment_mode` |

**Key decisions:**
- Enrichment block is built server-side from `state_json`, never sent from frontend.
- Frontend always sends `history: []` — enrichment replaces it entirely.
- `enrichment_block` is injected as a `system`-role message ("## Previous Context") so the LLM treats it as factual background.
- Backward-compat: old sessions without `result_uuid` on turns fall back to `created_at`/`timestamp` lookup in `chat_query_results`.
- 409 retry uses exponential backoff: 1s, 2s, 4s.

### Phase 3: Summarization ✅ (2026-07-21)

**Plan source:** `full-plan.md` §3

**Files modified:**

| File | Changes |
|---|---|
| `backend/llm_client.py` | **New file.** `summarize_turns()` function — calls LLM with summarization prompt, returns 2-3 sentence summary |
| `backend/api.py` | Added `SummarizeContextRequest`/`Response` schemas; `POST /sessions/{id}/summarize-context` endpoint with idempotency (returns existing if already covered), optimistic locking (version check + 409), builds thread text from turns, saves to `context_summaries[tag]` |
| `frontend/src/api/client.ts` | Added `summarizeContext()` function with retry |
| `frontend/src/sections/ChatSection.tsx` | Added `summarizingTags` state, `summaryTimerRef`, debounced summary trigger `useEffect` (mode-aware), `triggerSummary()` with 5s timeout fallback, "Summarizing..." UI indicator; persist `context_summaries` in `persistTurns()` |

**Key decisions:**
- RESEARCH mode: counts turns per tag (`aim:X`, `dataset:Y`), triggers summary every 5 turns per tag (provided they aren't already covered by an existing summary).
- SUMMARY mode: counts ALL turns, triggers global summary under `__all__` key every 5 total turns.
- Debounced at 2s — only the last trigger in a rapid-fire flurry survives.
- Idempotency on backend: if all turn timestamps are already covered by an existing summary entry, returns it without calling LLM.
- Frontend timeout: 5s — hides "Summarizing..." and continues without summary if LLM fails.

### Phase 4: Mode Management + Attachment Control ✅ (2026-07-21)

**Plan source:** `full-plan.md` §5, gap-analysis.md

**Files modified:**

| File | Changes |
|---|---|
| `frontend/src/stores/sessionStore.ts` | Added `setEnrichmentMode` action |
| `frontend/src/sections/ChatSection.tsx` | Added RESEARCH/SUMMARY toggle above composer; dataset search hidden in SUMMARY mode; AimBar hidden in SUMMARY mode; attach chips hidden in SUMMARY mode; composer placeholder changes per mode; `aimProposals` section rendered (only in RESEARCH); unified `selectedAims` state (removed local `useState`, use store only); removed sync `useEffect` |
| `frontend/src/sections/OutputPanel.tsx` | Added "+ Add"/"Added" toggle on each result card (adds/removes from `selectedAims`); added "Show Context" expandable view showing enrichment summaries + recent turns for that aim |

**Key decisions:**
- RESEARCH mode: full UI (dataset search, attach area, AimBar, analysis actions, aim proposals)
- SUMMARY mode: minimal UI (chat only, no attach/analysis/proposals)
- Mode toggle is a pill-button pair above the composer
- `selectedAims` unified to single source of truth (Zustand store), eliminating sync bugs
- `aimProposals` rendered in a "Suggested by LLM" section above AimBar
- OutputPanel context view shows existing summaries + recent turns for quick enrichment preview

### Phase 5: Prompt Engineering ✅ (2026-07-21)

**Plan source:** `full-plan.md` §4c, §5

**Files modified:**

| File | Changes |
|---|---|
| `backend/llm_client.py` | Added `ENRICHMENT_INSTRUCTION` (shared text explaining `[Summary]`/`[Turn]` format), `RESEARCH_SYSTEM_PROMPT` (generate SQL + proposals + actions), `SUMMARY_SYSTEM_PROMPT` (recap only, no queries), `build_enrichment_system_prompt()` (selects prompt by mode) |
| `backend/aims.py` | Imports `build_enrichment_system_prompt`; `generate_chat_response()` uses mode-specific prompts when enrichment block provided, falls back to existing `CHAT_SYSTEM_PROMPT` otherwise |
| `backend/api.py` | Passes `enrichment_mode` to `generate_chat_response` when using enrichment block |

**Key decisions:**
- `ENRICHMENT_INSTRUCTION` is a shared block explaining how to interpret `[Summary]` and `[Turn]` entries — included in both mode prompts.
- RESEARCH prompt explicitly allows generating SQL, proposing aims/actions, and instructs the LLM to prefix action proposals with `[Action]` for frontend parsing.
- SUMMARY prompt strictly prohibits new SQL or proposals — tells LLM to suggest switching to RESEARCH if asked.
- When no enrichment block is provided (backward compat), the original `CHAT_SYSTEM_PROMPT` is used unchanged.
