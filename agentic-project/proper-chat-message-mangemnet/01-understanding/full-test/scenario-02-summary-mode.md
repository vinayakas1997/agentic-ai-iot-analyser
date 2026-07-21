# Scenario 02: SUMMARY Mode Flow

## ID
`SCENARIO-02`

## Name
Basic SUMMARY Mode — Message Send, Guard Behavior, No SQL

## What It Tests
- End-to-end message flow in SUMMARY mode
- UI elements hidden in SUMMARY mode (dataset search, AimBar, attach chips)
- LLM uses SUMMARY prompt (recap only, no SQL/proposals)
- The dataset guard at `api.py:556` when no datasets are attached

## Why This Matters
SUMMARY mode is the minimal-chat mode for recap/discussion of existing analysis. The guard bug (B1) could block ALL SUMMARY messages if no datasets are attached, making the mode unusable without first having datasets selected.

## Preconditions
- Backend running
- Frontend running
- Fresh session

## Steps

### Step 1 — Switch to SUMMARY mode
| Action | Expected |
|--------|----------|
| Click SUMMARY pill toggle | `enrichmentMode` changes to `"summary"` in Zustand store |
| Check UI elements | Dataset search hidden, AimBar hidden, attach chips hidden |
| Check composer placeholder | Changes to "Ask for a summary of your analysis..." |

### Step 2 — Send a message (no datasets attached)
| Action | Expected |
|--------|----------|
| Type a question and press Enter | |
| **Expected (bug-free):** | Message is sent, LLM recaps, no SQL generated |
| **Expected (with B1):** | Backend returns "Please select at least one dataset...", no LLM call |
| Check API request | `POST /api/v2/messages` with `enrichment_mode: "summary"`, `attached_aims: []`, `line_name: ""` |
| Check backend logic flow | Line 553 guard checks `enrichment_mode == "research"` → false (it's "summary"), falls to line 556: `if not dataset_names` → true (empty) → returns static message |

### Step 3 — Verify response
| Action | Expected |
|--------|----------|
| Check response | If B1 is present: static "Please select at least one dataset" message. If fixed: actual LLM summary response. |
| Check enrichment block | If enrichment was built, it uses MODE-specific prompts with SUMMARY system prompt |

### Step 4 — Attach a dataset and repeat
| Action | Expected |
|--------|----------|
| Switch to RESEARCH, attach a dataset, switch back to SUMMARY | |
| Send a message | Now `dataset_names` is non-empty, guard passes, LLM called with SUMMARY prompt |
| Check LLM response | Recaps existing analysis, does NOT generate SQL or propose actions |

### Step 5 — Verify no SQL/proposals in response
| Action | Expected |
|--------|----------|
| Check `aim_proposals` | Empty array (SUMMARY prompt prohibits proposals) |
| Check `analysis_actions` | Empty array (SUMMARY prompt prohibits actions) |
| Check AimBar | Hidden in SUMMARY mode (cannot run SQL) |

## Bugs to Watch
- **B1 (CRITICAL):** SUMMARY mode with no datasets attached → blocked by guard at `api.py:556`. The guard checks `enrichment_mode == "research"` first (line 554), but even if that's false, line 556 checks `dataset_names` and blocks the message. This means SUMMARY mode without datasets is broken.
- Verify the `history` field in the API request: frontend should send `history: []` in SUMMARY mode too (enrichment replaces it).

## Status
NOT RUN

## Actual Result
*(Fill after running)*

## Notes
*(Fill after running)*
