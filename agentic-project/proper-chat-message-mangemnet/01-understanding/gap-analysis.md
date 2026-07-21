# Gap Analysis — Current UI vs New Architecture

## Overview

Before integrating the tagged context enrichment system, the current aim/dataset management UI has several gaps that directly conflict with the new architecture's requirements. In the new system, **what's attached to the composer determines what the LLM sees in enrichment**. This makes aim attachment control critical — something the current UI lacks entirely for LLM-proposed analysis actions.

---

## Gap 1: LLM-Analyzed Aims Are Always Auto-Attached

**Current behavior:** `handleRunAnalysis` (ChatSection.tsx:304-376) immediately:
- Adds the aim to `selectedAims`
- Attaches all datasets
- Runs the SQL query

The user has zero control. Every analysis action the LLM proposes is automatically attached and executed.

**Problem for new architecture:** If aims are always auto-attached, the user can't control enrichment scope. Every LLM-proposed analysis action would immediately enter the enrichment context, even if the user doesn't want it. This defeats the purpose of the composer being the "intent selector."

**Needed:** A two-step flow:
1. Show the action with an "Add for analysis" toggle (like datasets show "Use"/"In-use")
2. User decides whether to attach it
3. Only then can they run it (via AimBar or a dedicated Run button)

**Implementation locations:**
- `TurnBubble.tsx`: analysis actions should render with "Add for analysis" toggle before the Run button
- `handleRunAnalysis`: should not auto-attach or auto-run. Instead, attach if toggle is on, then wait for Run click.

---

## Gap 2: No "Add for Analysis" / "Added for Analysis" Toggle

**Current behavior:** In `TurnBubble.tsx`, analysis actions render as clickable pills:
- Default state: violet pill with play icon (`▶`) — clicking immediately runs
- Loading state: gray pill with pulsing dot — disabled
- Completed state: green pill with checkmark (`✓`) — clicking scrolls to result

There is no intermediate "should I add this?" state.

**Comparable UI that works:** In `ContextSection.tsx`, datasets have three states:
| State | Button | Click Action |
|---|---|---|
| Not attached | "Use" (accent text) | Attaches dataset |
| Attached | "In-use" (teal text) | Detaches dataset |
| Locked by aim | "Locked" (amber, disabled) | Nothing (tooltip explains) |

**Needed:** Same three-state pattern for analysis actions:

| State | Action Button | Click Action |
|---|---|---|
| Not attached | "Add for analysis" | Attaches aim + datasets to composer |
| Attached | "Added for analysis" (teal) | Detaches aim + unneeded datasets |
| Completed + attached | "Added ✓" (green) | Detaches aim |
| Completed + detached | "View" (scroll to result) | Just scrolls (no attach) |

This toggle should appear in three places:
1. **TurnBubble** — on each analysis action pill
2. **OutputPanel** — on each aim result card
3. **Analyses bar** — on each completed action chip

---

## Gap 3: Output Panel Aim Cards Lack Actions

**Current behavior:** Output panel result cards show:
- Aim name + row count + timestamp
- Delete button (trash icon — removes from output only, not from enrichment context)
- Show Details toggle (SQL, table, chart, CSV download)

**Missing for new architecture:**
1. **"Add/Added for analysis" toggle** — controls whether this aim enters the enrichment context
2. **Expandable context view** — shows the tag-filtered history for this aim:
   - Summary of previous turns tagged with this aim
   - SQL queries and results from those turns
   - What the LLM would see if this aim is attached (enrichment preview)

This gives the user visibility into what the LLM knows and why it answered a certain way.

**Implementation:** `OutputPanel.tsx` — add a toggle button next to the trash icon, and an expandable context section below the details section.

---

## Gap 4: `aimProposals` From LLM Are Never Rendered

**Current behavior:** `sessionStore.ts` accumulates `aimProposals` from backend responses (line 322-328):
```typescript
if (res.aim_proposals?.length) {
  set((state) => {
    const seen = new Set(state.aimProposals.map((p) => p.aim));
    const fresh = res.aim_proposals!.filter((p) => !seen.has(p.aim));
    return fresh.length ? { aimProposals: [...state.aimProposals, ...fresh] } : {};
  });
}
```

But `ChatSection.tsx` never renders `aimProposals`. The only visible suggested aims come from dataset metadata (`suggested_aims` field in the search panel). The LLM-proposed aims are silently stored and accumulate indefinitely.

**Problem for new architecture:** In RESEARCH mode, the LLM should suggest exploration paths via `aimProposals`. If these are never shown, the user misses the LLM's guidance on what to analyze next.

**Needed:** A visible UI section showing LLM-proposed aims, each with:
- Aim name + description
- "Add for analysis" toggle
- Preview button (opens PreviewModal)
- Datasets the aim references

**Where to render:** Three options (team decision needed):
1. **In the chat bubble** (alongside analysis actions) — most contextual
2. **In a separate "Proposals" section above the composer** — always visible, like suggested aims
3. **In the context panel** — separate from chat flow

Recommendation: Option 2 (separate section above composer) because it mimics the existing suggested-aims pattern.

---

## Gap 5: Bug — `errorState` Undefined in `handleRunAimSql`

**Location:** `ChatSection.tsx` lines 287-290 (inside the catch block of `handleRunAimSql`)

The code references `errorState` but it's never declared in that scope. The analysis action handler (line 356) correctly declares:
```typescript
const errorState: QueryResultState = { loading: false, error: clean };
```

But the aim SQL handler uses `errorState` without declaring it:
```typescript
// WRONG — errorState is not defined:
useOutputStore.getState().addResult({ result: errorState });
useSessionStore.setState((s) => ({
  chatQueryResults: { ...s.chatQueryResults, [now]: errorState },
}));
setQueryResults((prev) => ({ ...prev, [now]: errorState }));
```

**Impact:** Runtime crash when an aim SQL execution fails. The user sees no error message and the whole catch block throws a ReferenceError.

**Fix:** Replace `errorState` with `resultState` (which IS declared in the catch block). Or add `const errorState = resultState;`.

---

## Gap 6: Dual State for `selectedAims`

**Current behavior:** Selected aims are maintained in two places:
1. Local `useState` in `ChatSection.tsx`: `const [selectedAims, setSelectedAims] = useState<Aim[]>(...)`
2. Zustand store: `useSessionStore.selectedAims`

They're synced via `useEffect` (lines 387-396):
```typescript
useEffect(() => {
  if (sessionId) {
    setSelectedAims(storeSelectedAims);
    // ...
  }
}, [sessionId, storeSelectedAims]);
```

And updated manually in multiple places with slightly different logic:
- `useAim()` updates both local and store
- `removeAim()` updates both local and store
- `handleRunAimSql()` updates both local and store
- `handleRunAnalysis()` updates only store (relying on the effect to sync)

**Risk:** The sync effect depends on `storeSelectedAims` reference changing. If a function updates the store but the array content stays the same (same objects), the effect won't fire and local state desynchronizes.

**Recommendation:** Unify into a single source of truth:
- Option A: Use only `useSessionStore.selectedAims` — subscribe directly, remove local state
- Option B: Use only local state — sync to store imperatively after every change (current approach, but more disciplined)

Recommendation: Option A is cleaner since the store is the persistence source. Replace `selectedAims` local state with direct store subscription.

---

## Gap 7: No Way to Remove Completed Actions From UI

**Current behavior:** The "Analyses:" bar (ChatSection.tsx:661-677) shows completed action chips:
```tsx
{Object.entries(completedActions).map(([name, timestamp]) => (
  <button onClick={() => handleScrollToTurn(timestamp)}>
    <span>✓</span> {name}
  </button>
))}
```

Each chip scrolls to the turn on click. But there's no remove button.

The output panel has per-card delete (trash icon — removes from output display only), but the completed actions bar doesn't.

**Problem for new architecture:** Completed actions are part of the enrichment context (`completedActions` is checked when building enrichment). If a user wants to exclude a completed action from future enrichment, they need to be able to remove it.

**Needed:** An `×` button on each completed action chip that:
1. Removes from `completedActions` (local state + session store)
2. Removes the associated result from `chatQueryResults` (cleanup)
3. Detaches the aim from `selectedAims` if attached
4. Detaches datasets if no other aim references them (existing `removeAim` logic)

---

## Gap 8: Single-Action Concurrency — No Feedback

**Current behavior:** `handleRunAnalysis` checks `if (!sessionId || runningAction) return` (line 301). If a user clicks a second analysis action while one is running, the click silently does nothing.

Similarly, `handleRunAimSql` checks `if (runningAim) return` implicitly via the AimBar's disabled state.

**Needed:** Visual feedback when an action is blocked:
- Disable the button with a tooltip: "Another analysis is running. Please wait."
- Or show a brief toast/notification

**Implementation:** In `TurnBubble.tsx`, when `runningAction` is set, disable all action buttons and show a cursor-not-allowed style. Add `title` attribute with explanation.

---

## Gap 9: `toggle` vs `attach`/`detach` Semantic Mismatch

**Current behavior:**
- `useDatasetStore.toggle()` adds/removes from BOTH `selected` and `attached`
- ContextSection's "Use"/"In-use" buttons use `attach`/`detach` which only affect `attached`
- `storeRemove` removes from both

**Result:** A dataset can be `selected` but not `attached`. It shows in the ContextSection list, but the "In-use" button appears even though it's selected (but not attached). The user might be confused about the state.

**Recommendation:** Align semantics:
- `toggle` should only affect `selected` — selecting/unselecting a dataset from search
- `attach`/`detach` should only affect `attached` — whether the dataset is "in use" for the composer
- Remove `toggle`'s dual behavior

This has a cascading effect: `toggle` is used in the search panel checkboxes. Those checkboxes should only select/unselect, not attach/detach. The "Use"/"In-use" buttons handle attachment separately.

---

## Gap 10: `aimProposals` Are Never Cleaned Up

**Current behavior:** `aimProposals` only gets entries removed when `useAim()` is called (ChatSection.tsx:154):
```typescript
aimProposals: s.aimProposals.filter(
  (p) => p.aim.toLowerCase() !== aim.aim.toLowerCase()
),
```

But never cleaned up when:
- Session is switched
- Aim is rejected/closed without using
- Session is reopened

**Impact:** `aimProposals` accumulates indefinitely, potentially with stale proposals from old responses.

**Fix:** Clear `aimProposals` on:
- `newSession()`
- `switchSession()` (let the new session's proposals load fresh)

---

## Gap 11: `result_uuid` Not Set on Any Turn

**Current behavior:** The `result_uuid` field doesn't exist on the `Turn` type or any turn object. When analysis actions or aim runs complete, their result is stored in `chatQueryResults` but there's no link from the turn to its specific result.

**Impact:** Without `result_uuid`, the enrichment builder has no way to look up the correct result for a specific turn. It falls back to the last-write-wins approach via `completedActions` — which attributes the latest result to ALL historical turns of the same aim.

**Fix:**
1. Add `result_uuid?: string` field to `Turn` interface in `types/manager.ts`
2. Set `result_uuid: crypto.randomUUID()` in `handleRunAimSql` and `handleRunAnalysis` when creating the turn
3. Store result in `chatQueryResults` using the same UUID
4. Persist and restore `result_uuid` alongside other turn fields

---

## Gap 12: `handleRunAimSql` Doesn't Populate `completedActions`

**Current behavior:** Only `handleRunAnalysis` adds entries to `completedActions`. AimBar runs via `handleRunAimSql` do not. This means:
- AimBar runs don't appear in the "Analyses:" bar
- There's no scroll-back to AimBar run turns
- AimBar runs are invisible in the enrichment context

**Fix:** In `handleRunAimSql`, after successfully getting the result, also add:
```typescript
useSessionStore.setState((s) => ({
  completedActions: { ...s.completedActions, [aimDef.aim]: turnId },
}));
setCompletedActions((prev) => ({ ...prev, [aimDef.aim]: turnId }));
```

---

## Gap 13: `aimProposals` Not Cleared in `newSession()`

**Current behavior:** `newSession()` in `sessionStore.ts:222-241` resets `turns`, `selectedAims`, `completedActions`, `chatQueryResults`, `executionEvents`, `pendingTurn` — but does NOT reset `aimProposals`.

**Impact:** When a user creates a new session, the old session's aim proposals leak into the new session. The user sees stale suggestions.

**Fix:** Add `aimProposals: []` to the `set()` call in `newSession()`. Also add `context_summaries: {}` and `enrichment_mode: "research"` for completeness.

---

## Gap 14: `Turn` Type Missing `aims`, `datasets`, `result_uuid` Fields

**Current behavior:** The `Turn` interface in `types/manager.ts:72-83` only has:
```typescript
export interface Turn {
  turn_index?: number;
  user: string;
  agent: string;
  ui: TurnUi | null;
  schema: SchemaSnapshot | null;
  created_at?: string;
  description?: string | null;
  benefits?: string | null;
  columns?: { dataset: string; name: string }[] | null;
  analysis_actions?: AnalysisAction[];
}
```
No `aims`, `datasets`, or `result_uuid` fields.

**Impact:** TypeScript will reject any code that tries to set `t.aims`, `t.datasets`, or `t.result_uuid` on a `Turn` object. All the tag-setting changes in the plan will fail to compile.

**Fix:** Add to the interface:
```typescript
result_uuid?: string;
aims?: string[];
datasets?: string[];
```

---

## How These Gaps Block the New Architecture

| Gap | Blocks | Reason |
|---|---|---|
| Gap 1 (auto-attach) | Enrichment scope | User can't control which aims enter enrichment context |
| Gap 2 (no toggle) | Enrichment scope | No way to add/remove aims from enrichment context manually |
| Gap 3 (output panel) | Context visibility, enrichment scope | No attach control from output; no way to preview what LLM knows |
| Gap 4 (aimProposals hidden) | RESEARCH mode UX | LLM-suggested paths never shown to user |
| Gap 5 (errorState bug) | Stability | Runtime crash on aim SQL failure — breaks testing |
| Gap 6 (dual state) | Reliability | State desync could cause enrichment to use stale or missing aims |
| Gap 7 (no remove completed) | Enrichment scope | Can't exclude completed actions from enrichment |
| Gap 8 (no concurrency feedback) | UX | Silent failure when actions are blocked |
| Gap 9 (toggle mismatch) | Dataset state | Confusion about which datasets are actually attached |
| Gap 10 (aimProposals cleanup) | Freshness | Stale proposals shown after session switch |
| Gap 11 (no result_uuid) | Enrichment correctness | Can't link turn to its specific result |
| Gap 12 (AimBar no completedActions) | visibility | AimBar runs invisible in Analyses bar and enrichment |
| Gap 13 (newSession miss) | Cleanliness | Stale state across sessions |
| Gap 14 (Turn type missing fields) | Compilation | TypeScript errors prevent implementation |
```typescript
aimProposals: s.aimProposals.filter(
  (p) => p.aim.toLowerCase() !== aim.aim.toLowerCase()
),
```

But never cleaned up when:
- Session is switched
- Aim is rejected/closed without using
- Session is reopened

**Impact:** `aimProposals` accumulates indefinitely, potentially with stale proposals from old responses.

**Fix:** Clear `aimProposals` on:
- `newSession()`
- `switchSession()` (let the new session's proposals load fresh)

---

## How These Gaps Block the New Architecture

| Gap | Blocks | Reason |
|---|---|---|
| Gap 1 (auto-attach) | Enrichment scope | User can't control which aims enter enrichment context |
| Gap 2 (no toggle) | Enrichment scope | No way to add/remove aims from enrichment context manually |
| Gap 3 (output panel) | Context visibility, enrichment scope | No attach control from output; no way to preview what LLM knows |
| Gap 4 (aimProposals hidden) | RESEARCH mode UX | LLM-suggested paths never shown to user |
| Gap 5 (errorState bug) | Stability | Runtime crash on aim SQL failure — breaks testing |
| Gap 6 (dual state) | Reliability | State desync could cause enrichment to use stale or missing aims |
| Gap 7 (no remove completed) | Enrichment scope | Can't exclude completed actions from enrichment |
| Gap 8 (no concurrency feedback) | UX | Silent failure when actions are blocked |
| Gap 9 (toggle mismatch) | Dataset state | Confusion about which datasets are actually attached |
| Gap 10 (aimProposals cleanup) | Freshness | Stale proposals shown after session switch |

---

## Recommended Fix Order

### Phase 1: Type & Bug Fixes (do first, independent of new architecture)
1. **Add `aims`, `datasets`, `result_uuid` to `Turn` type** in `types/manager.ts` (Gap 14) — **critical, compilation fails without this**
2. Fix `errorState` bug in `handleRunAimSql` catch block (Gap 5) — **critical, blocks testing**
3. Fix `aimProposals` cleanup on `newSession()` (Gap 13)
4. Fix `toggle` vs `attach`/`detach` semantic mismatch (Gap 9)

### Phase 2: Tagging Infrastructure (pre-requisite for new architecture)
5. Unify `selectedAims` state — remove local state, use only store (Gap 6)
6. Add `result_uuid` to turn creation in `handleRunAimSql` and `handleRunAnalysis` (Gap 11)
7. Add `completedActions` update in `handleRunAimSql` (Gap 12)
8. Set `aims` and `datasets` on every turn at creation time

### Phase 3: Attachment Control (core for new architecture enrichment scope)
9. Add "Add/Added for analysis" toggle to TurnBubble analysis actions (Gap 2, location 1)
10. Change `handleRunAnalysis` to respect toggle — no auto-attach, no auto-run (Gap 1)
11. Add remove button to completed actions bar (Gap 7)
12. Add "Add/Added for analysis" toggle to OutputPanel aim cards (Gap 2, location 2)

### Phase 4: Visibility (for new architecture transparency)
13. Render `aimProposals` from LLM in a visible section (Gap 4)
14. Add expandable context view on output aim cards (Gap 3)
15. Show attached aims in ContextSection alongside datasets
16. Add concurrency feedback for blocked actions (Gap 8)

---

## File-by-File Impact of These Gaps

| File | Gaps | Changes Needed |
|---|---|---|
| `types/manager.ts` | 14 | Add `aims`, `datasets`, `result_uuid` to `Turn` interface |
| `ChatSection.tsx` | 1, 2, 5, 6, 7, 8, 11, 12, 13 | Fix errorState bug; add toggle logic to handleRunAnalysis; unify selectedAims state; tag turns with aims/datasets/result_uuid; add completedActions to handleRunAimSql; add remove to completed actions; clear aimProposals on newSession; send attached_aims + enrichment_mode; add summary trigger logic |
| `TurnBubble.tsx` | 1, 2, 8 | Add "Add/Added" toggle to action pills; add concurrency feedback (disable state + tooltip) |
| `OutputPanel.tsx` | 2, 3 | Add "Add/Added" toggle on result cards; add expandable context view |
| `AimBar.tsx` | 1, 6 | May need to read from single source of truth |
| `ContextSection.tsx` | 9 | Fix toggle vs attach/detach semantics; show attached aims |
| `sessionStore.ts` | 6, 10, 11, 13 | Unify selectedAims; clear aimProposals/context_summaries/enrichment_mode on newSession; restore enrichment_mode; restore result_uuid/aims/datasets on turns |
| `datasetStore.ts` | 9 | Fix toggle to only affect selected; keep attach/detach separate |
