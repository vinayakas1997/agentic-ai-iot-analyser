# Scenario 06: SUMMARY Mode Flow

## ID
`SCENARIO-06`

## Name
SUMMARY Mode — Recap & Summarize Only

## What It Tests
- SUMMARY mode: no dataset search, no AimBar, no suggested aims
- LLM receives SUMMARY_SYSTEM_PROMPT (no new SQL generation)
- LLM recaps findings from enrichment context
- Mode toggle switches to SUMMARY, UI adapts

## Why This Matters
SUMMARY mode is the read-only view. Users should be able to review past analyses without generating new queries.

## Preconditions
- Backend running
- Frontend running
- Fresh session with at least 1 existing turn (from RESEARCH mode)

## Steps

### Step 1 — Have a RESEARCH conversation first
| Action | Expected |
|--------|----------|
| Attach dataset, send 2-3 messages | Session has turns with agent responses |
| Verify turns exist | `sessionStore.getState().turns` has entries |

### Step 2 — Switch to SUMMARY mode
| Action | Expected |
|--------|----------|
| Click SUMMARY toggle | `enrichmentMode === "summary"` |
| Check UI | Dataset search hidden, AimBar hidden, attach chips hidden |
| Check composer placeholder | "Summarize findings, compare analyses, ask about past results..." |

### Step 3 — Send a summary question
| Action | Expected |
|--------|----------|
| Type "Summarize what we found" and send | LLM recaps findings |
| Check enrichment | Enrichment block built from ALL context summaries (`__all__` key) |
| Check response | No SQL proposals, no [Action] prefixes, no aim suggestions |

### Step 4 — Try to generate new analysis
| Action | Expected |
|--------|----------|
| Type "Run a new analysis on revenue" | LLM suggests switching to RESEARCH mode |
| Check response | "I'm in SUMMARY mode. Switch to RESEARCH to run new queries." |

## Bugs to Watch
- If dataset search or AimBar appears in SUMMARY mode → BUG
- If LLM proposes SQL or [Action] in SUMMARY mode → BUG (prompt issue)
- If mode switch is disabled during loading → should be (covered by cond-11)

## Status
NOT RUN

## Actual Result
*(Fill after running)*

## Notes
*(Fill after running)*
