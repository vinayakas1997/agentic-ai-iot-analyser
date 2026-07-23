# Scenario 07: Mode Switching

## ID
`SCENARIO-07`

## Name
RESEARCH ↔ SUMMARY Mode Switch

## What It Tests
- Toggle between RESEARCH and SUMMARY modes
- UI elements appear/hide based on mode
- Mode persisted to session state
- Mode restored on session load
- Mode switch disabled during loading (cond-11)

## Preconditions
- Backend running
- Frontend running
- Fresh session

## Steps

### Step 1 — Default mode
| Action | Expected |
|--------|----------|
| Check default | `enrichmentMode === "research"` |
| Check UI | Dataset search visible, AimBar area present |

### Step 2 — Switch to SUMMARY
| Action | Expected |
|--------|----------|
| Click SUMMARY | Mode changes to `summary` |
| Check UI | Dataset search hidden, AimBar hidden, attach chips hidden |
| Check composer placeholder | "Summarize findings..." |

### Step 3 — Switch back to RESEARCH
| Action | Expected |
|--------|----------|
| Click RESEARCH | Mode changes to `research` |
| Check UI | Dataset search visible, AimBar visible |

### Step 4 — Persist mode
| Action | Expected |
|--------|----------|
| Send a message in RESEARCH mode | `enrichment_mode: "research"` sent to backend |
| Check `PATCH` request | `enrichment_mode: "research"` persisted |

### Step 5 — Restore mode on session load
| Action | Expected |
|--------|----------|
| Refresh page / switch sessions | Mode restored from backend state |

### Step 6 — Mode switch disabled during loading
| Action | Expected |
|--------|----------|
| Send a message | `loading: true` |
| Try to click SUMMARY | Disabled (`cursor-not-allowed`, `opacity-50`) |
| Wait for response | Mode switch re-enabled |

## Bugs to Watch
- If mode switch is NOT disabled during loading → BUG
- If mode doesn't persist after refresh → BUG
- If UI elements don't update when mode changes → BUG

## Status
NOT RUN

## Actual Result
*(Fill after running)*

## Notes
*(Fill after running)*
