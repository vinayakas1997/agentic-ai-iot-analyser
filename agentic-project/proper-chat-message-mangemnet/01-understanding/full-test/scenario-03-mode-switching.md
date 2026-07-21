# Scenario 03: Mode Switching

## ID
`SCENARIO-03`

## Name
Toggle Between RESEARCH and SUMMARY Modes

## What It Tests
- UI elements appear/disappear correctly when toggling
- `enrichmentMode` persisted via `persistTurns()` and restored on reload
- `selectedAims` preserved across mode switches
- Enrichment block changes based on mode when sending messages

## Why This Matters
Users may switch modes mid-conversation. Mode state must persist, UI must be consistent, and the enrichment block must use the correct mode-specific prompt after each switch.

## Preconditions
- Backend running
- Frontend running
- Fresh session with at least one dataset selected and one aim attached

## Steps

### Step 1 — Start in RESEARCH, attach data
| Action | Expected |
|--------|----------|
| Confirm RESEARCH mode active | Dataset search, AimBar, attach chips visible |
| Attach a dataset + aim | `selectedAims` has entry, datasets attached |
| Send 2-3 messages | Turns created with enrichment |

### Step 2 — Switch to SUMMARY
| Action | Expected |
|--------|----------|
| Click SUMMARY pill | `enrichmentMode` changes to `"summary"` |
| Check `selectedAims` | Still preserved in Zustand store |
| Check UI | Dataset search hidden, AimBar hidden, attach chips hidden |
| Send a message | Enrichment block built with SUMMARY prompt, LLM recaps only |

### Step 3 — Switch back to RESEARCH
| Action | Expected |
|--------|----------|
| Click RESEARCH pill | `enrichmentMode` changes back to `"research"` |
| Check UI | Dataset search visible, AimBar visible, attach chips visible |
| Check `selectedAims` | Still preserved |
| Send a message | Enrichment block built with RESEARCH prompt, LLM can generate SQL/proposals |

### Step 4 — Verify persistence
| Action | Expected |
|--------|----------|
| Refresh the page | `bootstrap()` restores session with `enrichmentMode` from `state_json` |
| Check mode toggle | Shows correct mode (whichever was set before refresh) |
| Check UI elements | Correct elements visible based on restored mode |

## Bugs to Watch
- **B6:** `updateSession` shallow merge could corrupt `enrichment_mode` if nested improperly in `state_json`
- Verify `persistTurns()` actually saves `enrichment_mode` field (it checks `if (enrichmentMode)` before persisting)

## Status
NOT RUN

## Actual Result
*(Fill after running)*

## Notes
*(Fill after running)*
