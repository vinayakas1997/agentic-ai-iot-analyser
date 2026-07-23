# Scenario 04: Dataset Locking & Removal

## ID
`SCENARIO-04`

## Name
Dataset Locking — Cannot Detach When Active Aim Uses It

## What It Tests
- Cond-15: Dataset attached to active aim shows locked icon
- Cond-15: User cannot manually detach dataset locked by aim
- Cond-15: Block message "This aim uses this dataset" appears on hover
- Cond-15: When aim is removed, dataset stays attached (no auto-detach)
- User can manually detach after aim is removed

## Why This Matters
Prevents orphaned state where an aim references a dataset that was detached. Gives user clear feedback about why the detach button is disabled.

## Preconditions
- Backend running
- Frontend running
- Fresh session
- At least one dataset available
- Need an aim that references that dataset (from search bar suggested aims or LLM proposals)

## Steps

### Step 1 — Attach aim with datasets
| Action | Expected |
|--------|----------|
| Find a suggested aim that references at least 1 dataset | |
| Click the aim | `useAim()` called → datasets auto-attached |
| Check dataset chip | Dataset appears in attached chips with locked icon (× disabled, `text-muted/40`) |
| Hover over X | Tooltip: "Locked by a selected aim — remove the aim first" |

### Step 2 — Try to detach manually
| Action | Expected |
|--------|----------|
| Click the detach × | Nothing happens (button is disabled) |
| Check Zustand dataset store | Dataset still attached |

### Step 3 — Remove the aim
| Action | Expected |
|--------|----------|
| Click × on the AIM in AimBar | `removeAim()` called, aim removed from `selectedAims` |
| Check dataset chip | Dataset still attached (no auto-detach) |
| Check detach × | Now clickable (no longer locked) |

### Step 4 — Manually detach after aim removal
| Action | Expected |
|--------|----------|
| Click dataset detach × | Dataset detached, chip removed |

### Step 5 — Test with multiple aims sharing a dataset
| Action | Expected |
|--------|----------|
| Attach aim1 (uses dataset A) | Dataset A locked |
| Attach aim2 (also uses dataset A) | Dataset A still locked |
| Remove aim1 | Dataset A still locked (aim2 still uses it) |
| Remove aim2 | Dataset A now unlocked |
| Detach dataset A | Dataset A removed |

## Bugs to Watch
- If dataset is auto-detached when aim is removed → BUG (should stay)
- If dataset detach button is NOT disabled when aim is active → BUG
- If locked tooltip doesn't show → BUG
- If dataset stays locked after ALL aims using it are removed → BUG

## Status
NOT RUN

## Actual Result
*(Fill after running)*

## Notes
*(Fill after running)*
