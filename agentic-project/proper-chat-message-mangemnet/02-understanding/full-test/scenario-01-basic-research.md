# Scenario 01: Basic RESEARCH Mode — Metadata-Only Flow

## ID
`SCENARIO-01`

## Name
Basic RESEARCH Mode — Message Send with Metadata-Only Enrichment

## What It Tests
- End-to-end message flow in RESEARCH mode: user types → no pre-analysis → LLM responds with metadata only
- LLM gets column metadata, dataset descriptions, suggested aims (no SQL results)
- Cross-dataset analysis prompt present when multiple datasets attached
- UI locking during loading prevents duplicate sends
- Turn created with `aims`, `datasets` populated

## Why This Matters
This is the primary user workflow. No auto-run (Option B from conditions). The LLM must be able to answer questions based on column metadata alone. All UI elements must be locked during loading.

## Preconditions
- Backend running on port 7010
- Frontend running on port 5173
- Fresh browser session (clear localStorage)
- Database has at least one dataset in `global_registry`

## Steps

### Step 1 — Create new session
| Action | Expected |
|--------|----------|
| Open the app | Auto-creates new session via `bootstrap()` |
| Check Zustand | `sessionId` is a UUID, `enrichmentMode === "research"` |

### Step 2 — Attach a dataset
| Action | Expected |
|--------|----------|
| Search and select a dataset | Dataset chip appears, `storeAttached` includes it |
| Check UI | Dataset name shown in attached chips area |

### Step 3 — Send a message
| Action | Expected |
|--------|----------|
| Type "What can you tell me about this data?" and press Enter | `sendUserMessage()` called with `history: []`, `enrichmentMode: "research"` |
| Check Send button | Disabled during loading |
| Check mode switch | Disabled during loading (opacity-50, cursor-not-allowed) |
| Check dataset detach | Disabled during loading |
| Check "Thinking..." | Loading spinner visible |

### Step 4 — Verify response
| Action | Expected |
|--------|----------|
| Check API response | `agent_message` present with analysis based on metadata |
| Check `aim_proposals` | LLM may propose aims based on metadata |
| Check `analysis_actions` | LLM may propose actions |
| Check no `result_uuid` | No SQL was executed (metadata only) |

### Step 5 — Check turn creation
| Action | Expected |
|--------|----------|
| Check Zustand turns | Turn has `aims: []`, `datasets: ["dataset_name"]` |
| Check TurnBubble UI | User message + agent response shown |

### Step 6 — UI re-enabled after response
| Action | Expected |
|--------|----------|
| Check mode switch | Enabled again |
| Check Send button | Enabled again |
| Check dataset detach | Enabled again |

## Bugs to Watch
- **B7 (FIXED):** `sessionId` rename would crash `sendUserMessage`

## Status
NOT RUN

## Actual Result
*(Fill after running)*

## Notes
*(Fill after running)*
