# Why — From Flat History to Tagged Context Enrichment

## The Original Problem

The existing chat system had a flat, wasteful approach to LLM context:

- **Turn structure**: Each turn had only `user`, `agent`, `timestamp`, and optional `analysis_actions`. No tagging — a turn didn't know which aim or dataset it belonged to.
- **LLM context**: Every message sent the last 10 raw turns as `history` to the LLM, regardless of relevance. This was token-heavy and provided no structured context.
- **Analysis results invisible to LLM**: When a user ran an aim via the AimBar or triggered an analysis action, the result (SQL, rows, charts) was stored in `chatQueryResults` and `outputStore` for UI rendering, but the turn's `agent` text was just a placeholder: `"**{name}** — results shown below."`. The LLM never saw the actual analysis data.
- **No follow-up capability**: A user could not ask "why were melons higher in summer?" after an analysis, because the LLM had zero context about what the analysis found.

## The Core Insight

The **composer is the intent selector**. What the user attaches (aims + datasets) directly defines what the LLM should know about. Sending a chronological dump of the last 10 turns wastes tokens and dilutes relevance.

## The Proposed Architecture

### 1. Tag every turn with `aims: string[]` and `datasets: string[]`

Each turn now carries metadata about which aim(s) and dataset(s) it relates to, assigned at creation time:

| Turn origin | Tags |
|---|---|
| Chat message (`/messages`) | Aims and datasets attached in the composer |
| AimBar RUN (`/execute-query`) | The specific aim + datasets it operates on |
| Analysis action (`/execute-query`) | The specific action name + datasets |

No duplication — each turn has exactly one tag set.

Additionally, each turn has a `result_uuid` field linking it to its specific result in `chat_query_results`. This ensures per-run result attribution (not last-write-wins).

### 2. Two modes: RESEARCH and SUMMARY

The mode determines enrichment strategy and LLM behavior:

| Mode | Enrichment | LLM Behavior |
|---|---|---|
| **RESEARCH** | Only turns whose tags intersect attached aims/datasets | Generate SQL, proposals, analysis actions |
| **SUMMARY** | All summaries + recent raw turns across the session | Recap findings, no new queries |

### 3. Summary pipeline (every 5 turns per tag)

To prevent context-window blowup while preserving signal:

- Every 5th turn for a given tag triggers a summary generation (frontend shows "Summarizing..." loading state).
- Idempotency check: only triggers if those turn timestamps aren't already covered by an existing summary.
- Debounced (2s) to prevent rapid-fire triggers on batch message sends.
- Summaries are stored in `state_json.context_summaries` keyed by `aim:{name}` or `dataset:{name}`.
- Enrichment = all previous summaries + recent 5 raw turns (not yet summarized) for the relevant tags.

### 4. Enrichment replaces `history`

The raw chronological `history` parameter is removed. Instead:

- RESEARCH: summaries + raw turns filtered by attached aims/datasets.
- SUMMARY: all summaries + recent raw turns across all tags.
- Backend ignores `history` if `enrichment_mode` is set (graceful fallback for stale clients).

## Key Decisions and Rationale

| Decision | Rationale |
|---|---|
| `enrichment_mode` not `mode` | Avoids collision with existing `ManagerSession.mode` DB column |
| `completed_actions` maps to turn timestamp | Preserves scroll-to-turn functionality in the UI |
| `result_uuid` on each turn | Ensures per-run result attribution, not last-write-wins |
| Summary idempotency check | Prevents duplicate summaries on reload or multi-tab |
| Dedup by ALL turn timestamps | Prevents dropping summaries that share a single turn but cover different ranges |
| Enrichment block size cap (4000 tokens) | Prevents context-window overflow |
| Backend guard for RESEARCH + no attachments | Returns early message without calling LLM (saves tokens) |
| Optimistic locking with `version` column | Prevents read-modify-write data loss from concurrent writers |

---

## Complete Issue Matrix (all 16 findings)

### Blocking (fix before implementation)

| # | Issue | How We Handle It |
|---|---|---|
| 1 | Mode field collision: `state_json.mode` conflicts with `ManagerSession.mode` DB column | Use `enrichment_mode` instead |
| 2 | Scroll-to-turn breaks: `completed_actions` pointing to result UUID loses the turn scroll target | `completed_actions` maps to turn timestamp (for scroll). Each turn carries `result_uuid` (for result lookup). Two separate fields. |
| 10 | LLM prompt template undefined: LLM won't know how to interpret enrichment block | Design prompt template before implementation: explain enrichment format, mode-specific behavior, when to generate SQL vs just answer |
| 11 | Migration for old `chat_query_results` keys: old sessions have timestamp keys, new sessions have UUID keys | Backward-compat check in `build_enrichment_block`: if turn has no `result_uuid`, fall back to looking up by `created_at` in old-format `chat_query_results` |
| 17 | `Turn` type definition in `types/manager.ts` missing `aims`, `datasets`, `result_uuid` fields | Add these fields to the `Turn` interface. Plan §1 now references this file. |
| 18 | Persistence field name mismatch: plan uses `created_at` but backend stores as `timestamp` | Keep `timestamp` as the persisted field name for backward compat with existing sessions. |

### High Priority (must be in first implementation phase)

| # | Issue | How We Handle It |
|---|---|---|
| 3 | Duplicate summaries on reload/multi-tab: `count % 5 === 0` retriggers | Frontend: check existing summaries before triggering. Backend: idempotency check on `/summarize-context` — if a summary already exists for those exact turn timestamps, return existing one |
| 4 | Dedup bug drops entire summaries: only checks first turn timestamp | Check ALL turn timestamps against `seen_timestamps`. Only skip if ALL turns are covered |
| 5 | Stale result attribution on aim re-run: `completed_actions` is last-write-wins | Per-turn `result_uuid` on the turn object. Enrichment uses the turn's own `result_uuid` to look up its specific result |
| 12 | Enrichment block size cap: 50+ turns could overflow context | Hard cap at 4000 tokens with token estimation in `build_enrichment_block`. Stop adding when limit reached |
| 19 | `handleRunAimSql` doesn't populate `completedActions` | Add `completedActions` update in `handleRunAimSql` so AimBar runs also appear in the "Analyses:" bar |

### Medium Priority (address during implementation)

| # | Issue | How We Handle It |
|---|---|---|
| 6 | No validation that `history` is empty: stale client could send full history | Backend ignores `history` if `enrichment_mode` is set. Log warning if non-empty |
| 7 | No backend gating for RESEARCH + no attachments: empty enrichment still calls LLM | Early return with `"Please attach a dataset or aim, or switch to SUMMARY mode."` before calling LLM |
| 8 | 80-char SQL truncation risks hallucination: truncated SQL mid-clause | Either include full SQL or add truncation marker: `"... [truncated]"` |
| 9 | Pre-existing `state_json` race condition: two concurrent writers can lose data | Use optimistic locking with `ManagerSession.version` column. Retry on 409 |
| 13 | Summary trigger needs debouncing: 5 rapid messages fire trigger 5 times | Debounce with 2s timer. Only fire once after batch completes |
| 20 | `aimProposals` not cleared in `newSession()` — stale proposals leak | Add `aimProposals: []` to the `newSession()` state reset alongside `context_summaries` and `enrichment_mode` |

### Low Priority (monitor / follow-up)

| # | Issue | How We Handle It |
|---|---|---|
| 14 | `execute-query` doesn't save turns (pre-existing): client crash loses the turn | Not in scope for this plan |
| 15 | Default `enrichment_mode` for existing sessions | Default to `"research"` |
| 16 | `persistTurns` payload grows over time: sends entire `chat_query_results` on every save | Monitor in production. Could optimize to delta-only pushes later |

### High Priority (must be in first implementation phase)

| # | Issue | How We Handle It |
|---|---|---|
| 3 | Duplicate summaries on reload/multi-tab: `count % 5 === 0` retriggers | Frontend: check existing summaries before triggering. Backend: idempotency check on `/summarize-context` — if a summary already exists for those exact turn timestamps, return existing one |
| 4 | Dedup bug drops entire summaries: only checks first turn timestamp | Check ALL turn timestamps against `seen_timestamps`. Only skip if ALL turns are covered |
| 5 | Stale result attribution on aim re-run: `completed_actions` is last-write-wins | Per-turn `result_uuid` on the turn object. Enrichment uses the turn's own `result_uuid` to look up its specific result |
| 12 | Enrichment block size cap: 50+ turns could overflow context | Hard cap at 4000 tokens with token estimation in `build_enrichment_block`. Stop adding when limit reached |

### Medium Priority (address during implementation)

| # | Issue | How We Handle It |
|---|---|---|
| 6 | No validation that `history` is empty: stale client could send full history | Backend ignores `history` if `enrichment_mode` is set. Log warning if non-empty |
| 7 | No backend gating for RESEARCH + no attachments: empty enrichment still calls LLM | Early return with `"Please attach a dataset or aim, or switch to SUMMARY mode."` before calling LLM |
| 8 | 80-char SQL truncation risks hallucination: truncated SQL mid-clause | Either include full SQL or add truncation marker: `"... [truncated]"` |
| 9 | Pre-existing `state_json` race condition: two concurrent writers can lose data | Use optimistic locking with `ManagerSession.version` column. Retry on 409 |
| 13 | Summary trigger needs debouncing: 5 rapid messages fire trigger 5 times | Debounce with 2s timer. Only fire once after batch completes |

### Low Priority (monitor / follow-up)

| # | Issue | How We Handle It |
|---|---|---|
| 14 | `execute-query` doesn't save turns (pre-existing): client crash loses the turn | Not in scope for this plan |
| 15 | Default `enrichment_mode` for existing sessions | Default to `"research"` |
| 16 | `persistTurns` payload grows over time: sends entire `chat_query_results` on every save | Monitor in production. Could optimize to delta-only pushes later |

---

## Caveats and How We Handle Them

### (A) Context-window blowup
**Risk**: Fetching too many turns blows context limits.  
**Mitigation**: Summary pipeline (every 5 turns) compresses history. Enrichment = summaries + only the most recent 5 raw turns per tag. Hard token cap (4000 tokens) with stop-adding behavior.

### (B) Summary generation latency
**Risk**: Generating a summary after every 5th turn adds latency.  
**Mitigation**: Frontend shows "Summarizing... getting ready" loading state. Summary call hits a dedicated endpoint (`POST /summarize-context`), so it doesn't block the message flow. Debounce prevents rapid-fire triggers.

### (C) No attachments in RESEARCH mode
**Risk**: User in RESEARCH mode sends a message with no aims/datasets attached.  
**Mitigation**: Backend returns early with "Please attach a dataset or aim, or switch to SUMMARY mode." — no LLM call is made, saving tokens.

### (D) Old sessions with no tags
**Risk**: Existing sessions have turns without `aims`/`datasets`. RESEARCH mode enrichment returns nothing.  
**Mitigation**: Untagged turns are included in SUMMARY mode enrichment but skipped in RESEARCH mode. Backward-compat check for old `chat_query_results` key format (timestamp vs UUID).

### (E) Duplicate turns in enrichment
**Risk**: A turn tagged with both aim A and dataset X appears twice when both are attached. Two summaries might share some but not all turn timestamps.  
**Mitigation**: Deduplication by checking ALL turn timestamps, not just the first one. A summary is only skipped if ALL its turns are already covered.

### (F) `chatQueryResults` key collision
**Risk**: Keys are timestamps; two actions completing in the same millisecond collide.  
**Mitigation**: Switch to UUID keys for `chatQueryResults`. Each turn has `result_uuid` linking to its specific result.

### (G) Cross-tag questions in RESEARCH mode
**Risk**: User detaches aim A, attaches aim B, asks "how does B compare with A?" — the LLM has no context for A.  
**Mitigation**: User must re-attach A. This is by design — explicit intent reduces token waste and ambiguity.

### (H) Stale result attribution
**Risk**: Running the same aim 3 times enriches all historical turns with the latest result.  
**Mitigation**: Per-turn `result_uuid` field links each turn to its own specific result. `completed_actions` is only used for scroll-to-turn, not for enrichment data lookup.

### (I) Concurrent state writes
**Risk**: `send_message` and `/summarize-context` both write to `state_json` concurrently, causing data loss.  
**Mitigation**: Optimistic locking using `ManagerSession.version` column. Both endpoints check and increment version on write. Frontend retries on 409.

### (J) Old `chat_query_results` key format
**Risk**: After migration, existing sessions have `chat_query_results` keyed by timestamp string, not UUID.  
**Mitigation**: `build_enrichment_block` first checks `turn.result_uuid` (new format), falls back to `turn.created_at` (old format) if not present.

### (K) SQL truncation without marker
**Risk**: Truncating SQL at 80 characters mid-clause causes LLM to hallucinate the missing part.  
**Mitigation**: Either include full SQL or append `"... [truncated]"` to the truncated value.
