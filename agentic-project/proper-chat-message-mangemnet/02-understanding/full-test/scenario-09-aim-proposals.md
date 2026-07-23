# Scenario 09: Aim Proposals & Analysis Actions

## ID
`SCENARIO-09`

## Name
Aim Proposals, Dataset Attachment, and Analysis Action Two-Step Flow

## What It Tests
- LLM-generated `aim_proposals` displayed in "Suggested by LLM" section
- Click proposal → `useAim()` → added to `selectedAims`, datasets attached
- LLM-generated `analysis_actions` shown as chips in TurnBubble
- Two-step flow: chip toggle attaches to composer, AimBar "Run" executes
- Four chip states: Add / Added / Completed+Added / View
- Dataset locking from active aims

## Why This Matters
The aim proposal system is the primary way users discover analyses. Dataset locking ensures data integrity.

## Preconditions
- Backend running
- Frontend running
- Fresh session with dataset attached
- LLM is generating proposals (requires a good prompt)

## Steps

### Step 1 — Get AI proposals
| Action | Expected |
|--------|----------|
| Attach dataset, send a well-crafted message | LLM returns `aim_proposals` array |
| Check UI | "Suggested by LLM" section appears above AimBar |

### Step 2 — Accept a proposal
| Action | Expected |
|--------|----------|
| Click a proposal | `useAim()` fires |
| Check `selectedAims` | Now includes `{ aim, description, datasets }` |
| Check proposals list | Accepted proposal removed from "Suggested by LLM" |
| Check dataset store | All datasets for the aim are attached |

### Step 3 — Dataset locking
| Action | Expected |
|--------|----------|
| Check dataset chips | Datasets from aim show locked icon |
| Try to detach | Disabled with tooltip: "Locked by a selected aim" |

### Step 4 — Analysis action chips in TurnBubble
| Action | Expected |
|--------|----------|
| Check TurnBubble | Action chips rendered below agent message |
| Default state | Violet pill with `+ ActionName` |
| Click to attach | Chip turns teal ("Added"), aim in composer |
| Click to detach | Chip returns to violet, aim removed from composer |

### Step 5 — Run from AimBar
| Action | Expected |
|--------|----------|
| Click RUN on an attached aim | SQL executes, result shown |
| Check chip state | Green pill with ✓ (completed + attached) |

## Bugs to Watch
- If dataset is NOT locked after aim accepted → BUG
- If accepted proposal stays in "Suggested by LLM" → BUG

## Status
NOT RUN

## Actual Result
*(Fill after running)*

## Notes
*(Fill after running)*
