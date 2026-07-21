# Scenario 01: Basic RESEARCH Mode Flow

## ID
`SCENARIO-01`

## Name
Basic RESEARCH Mode — Message Send, Enrichment, SQL Execution

## What It Tests
- End-to-end message flow in RESEARCH mode: user types → enrichment block built → LLM responds → proposals/actions extracted → turn saved
- SQL execution via AimBar (`handleRunAimSql`)
- Turn created with `aims`, `datasets`, `result_uuid` populated
- Dual turn creation: one chat turn from `sendUserMessage`, one synthetic turn from `handleRunAimSql`

## Why This Matters
This is the primary user workflow. If this breaks, the entire system is unusable. The dual-turn creation pattern (chat turn + synthetic SQL turn) is a key architectural choice that must work end-to-end.

## Preconditions
- Backend running on port 8000
- Frontend running on port 5173
- Fresh browser session (clear localStorage)
- Database has at least one dataset in `global_registry`

## Steps

### Step 1 — Create new session
| Action | Expected |
|--------|----------|
| Open the app | Auto-creates new session via `bootstrap()` with no existing sessions |
| Check Zustand | `sessionStore.getState().sessionId` is a UUID, `isLocalSession: true` initially, then `false` after first API call |

### Step 2 — Verify RESEARCH mode is default
| Action | Expected |
|--------|----------|
| Check mode toggle | `enrichmentMode === "research"`, RESEARCH pill is active |
| Check UI elements | Dataset search visible, AimBar visible, attach chips hidden (no attachments yet) |

### Step 3 — Select a dataset
| Action | Expected |
|--------|----------|
| Use dataset search | Datasets loaded from `GET /api/v2/datasets` |
| Click a dataset | Dataset store updated, `storeAttached` includes it, chip shown |

### Step 4 — Send a message
| Action | Expected |
|--------|----------|
| Type message and press Enter | `sendUserMessage()` called with `history: []`, `enrichmentMode: "research"`, `attachedAims: []`, `attachedDatasets: ["dataset_name"]` |
| Check API request | `POST /api/v2/messages` with body: `{ session_id, message, line_name: "dataset_name", attached_aims: [], enrichment_mode: "research", history: [] }` |
| Check backend logs | "Building enrichment block" logged, "History replaced by enrichment" logged |
| Check response | `agent_message`, `aim_proposals` (possibly empty), `analysis_actions` (possibly empty), no `result_uuid` |

### Step 5 — Verify turn created
| Action | Expected |
|--------|----------|
| Check Zustand turns | `sessionStore.getState().turns` has 1 entry with `aims: []`, `datasets: ["dataset_name"]` |
| Check TurnBubble UI | Shows user message + agent response, no action chips (no aims attached) |
| Check DB | `state_json.turns` has 1 entry, `version` incremented to 2 (was 1 from creation) |

### Step 6 — Attach an aim from proposals (if any)
| Action | Expected |
|--------|----------|
| If `aim_proposals` present | "Suggested by LLM" section shows proposals |
| Click a proposal | `useAim()` called → aim added to `selectedAims`, datasets attached, proposal removed from list |
| Check Zustand | `selectedAims` has 1 entry with `{ aim, description, datasets }` |

### Step 7 — Run SQL via AimBar
| Action | Expected |
|--------|----------|
| Type a query in composer or use an existing aim chip | Click "Run" on AimBar |
| Check API request | `POST /api/v2/execute-query` called with `message`, `line_name`, `history` |
| Check response | `sql`, `columns`, `column_types`, `rows`, `row_count`, `chart_suggestions` |
| Check synthetic turn | New turn created with `created_at` = UUID (from `crypto.randomUUID()`), `result_uuid` = same UUID |

### Step 8 — Verify result appears
| Action | Expected |
|--------|----------|
| Check OutputPanel | Result card shows with SQL, data table, and chart |
| Check "+ Add" button | Present on result card |
| Check `chatQueryResults` | `sessionStore.getState().chatQueryResults[turnId]` has full result state |

## Bugs to Watch
- **B5:** If `generate_aim` import fails, `POST /api/v2/aim/new-research` crashes with 500
- **B3:** The synthetic turn from Step 7 has `created_at` = UUID, not ISO timestamp — verify this doesn't break anything downstream

## Status
NOT RUN

## Actual Result
*(Fill after running)*

## Notes
*(Fill after running)*
