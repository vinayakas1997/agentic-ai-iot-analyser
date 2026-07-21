# Scenario 08: Aim Proposals & Analysis Actions

## ID
`SCENARIO-08`

## Name
Aim Proposal Display, Acceptance, and Analysis Action Two-Step Flow

## What It Tests
- LLM-generated `aim_proposals` displayed in "Suggested by LLM" section
- Click proposal → `useAim()` → added to `selectedAims`, datasets attached, proposal removed
- LLM-generated `analysis_actions` shown as chips in TurnBubble
- Two-step flow: chip toggle attaches to composer, AimBar "Run" executes
- Four chip states: Add (default) / Added (teal) / Completed+Added (green) / View
- Re-run (↻) and remove (×) on completed actions bar
- OutputPanel "+ Add"/"Added" toggle on result cards

## Why This Matters
The aim proposal + action system is the primary way users discover and execute analyses. The two-step flow (toggle + run) is a new UX pattern that replaced the old single-step `handleRunAnalysis`.

## Preconditions
- Backend running
- Frontend running
- Fresh session with dataset attached
- LLM is generating proposals (requires a good prompt)

## Steps

### Step 1 — Get AI proposals
| Action | Expected |
|--------|----------|
| Attach dataset, send a well-crafted message | LLM should return aim proposals with `[Action]` prefix |
| Check response | `aim_proposals` array has entries with `{ aim, description, datasets }` |
| Check UI | "Suggested by LLM" section appears above AimBar with proposals |

### Step 2 — Accept a proposal
| Action | Expected |
|--------|----------|
| Click a proposal | `useAim()` fires |
| Check `selectedAims` | Now includes `{ aim: "proposal_name", description: "...", datasets: [...] }` |
| Check proposals list | Accepted proposal removed from "Suggested by LLM" |
| Check dataset store | All datasets associated with the aim are attached via `storeAddMultiple` + `storeAttachMultiple` |

### Step 3 — Analysis action chips in TurnBubble
| Action | Expected |
|--------|----------|
| Check TurnBubble for chips | Action chips rendered below the agent message |
| Default state | Violet chip with aim name, togglable |
| Click a chip (attach) | Chip turns teal ("Added"), aim attached to composer |
| Click again (detach) | Chip returns to violet, aim removed from composer |

### Step 4 — Run attached action
| Action | Expected |
|--------|----------|
| With a teal chip, click "Run" on AimBar | `handleRunAimSql()` executes |
| Check chip after execution | Turns green ("Completed+Added") with checkmark |
| Check completed actions bar | Shows pill with aim name, re-run (↻) button, remove (×) button |

### Step 5 — Re-run and remove
| Action | Expected |
|--------|----------|
| Click re-run (↻) | `handleRerunAim()` re-executes SQL for that aim |
| Click remove (×) | `handleRemoveCompletedAction()` removes from `completedActions`, removes from `selectedAims` if present |

### Step 6 — OutputPanel "+ Add" toggle
| Action | Expected |
|--------|----------|
| Run SQL on an aim | Result card appears in OutputPanel |
| Click "+ Add" on result card | Aim added to `selectedAims`, button changes to "Added" (teal) |
| Click "Added" | Aim removed from `selectedAims`, button changes back to "+ Add" |
| **B2 check:** | Are orphaned datasets detached? `removeAim()` in ChatSection checks this. OutputPanel's toggle does NOT call `removeAim()`, so datasets remain attached. |

## Bugs to Watch
- **B2:** OutputPanel "+ Add"/"Added" toggle does NOT detach orphaned datasets when removing (unlike `removeAim()` in ChatSection which checks for orphaned datasets). After toggling an aim off in OutputPanel, its datasets remain attached. Check in DatasetStore if orphaned datasets persist.
- Verify `analysis_actions` extraction uses the correct `[Action]` prefix parsing in `extract_analysis_actions()`
- Verify `max_aims` in `extract_analysis_actions` limit (how many actions default to)

## Status
NOT RUN

## Actual Result
*(Fill after running)*

## Notes
*(Fill after running)*
