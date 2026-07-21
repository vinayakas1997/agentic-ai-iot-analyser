# Plan: Aim Results → Right-Side OutputPanel (Timeline)

## Goal
Move aim SQL results from ChatSection local state + modal into a persistent OutputPanel timeline. Chat stays lean; results accumulate independently.

## Current State (verified)
- `ChatSection.tsx:345` — `aimResults` is local React state; `expandedAimResult` modal at lines 850–882
- `OutputPanel.tsx` — empty placeholder
- `App.tsx:22` — 3-column grid: Context | Chat | OutputPanel, responsive to single column on mobile
- `lib/styles.ts` — `resultCardClass`, `miniTableClass`, `insightNoteClass` already defined
- `sessionStore.ts` — `aimProposals` already persisted to backend `state_json["aim_proposals"]`

## Design Decisions

### 1. Persistence: Output results saved to backend `state_json["output_results"]`
**Decision:** Persist results to backend on every add/remove/clear. This aligns with the project's "persistent across page refresh" objective and follows the existing `aimProposals` pattern.

- Backend already accepts arbitrary `state_json` via `PATCH /api/v2/sessions/{id}` (used for `aimProposals`).
- `sessionStore` needs an `updateOutputResults(results)` action that calls `api.updateSessionTitle`-style PATCH with `state: { output_results: [...] }`.
- On `bootstrap` and `switchSession`, load `output_results` from session `state` into the output store.

### 2. `outputStore.ts` — New global Zustand store
```ts
interface CollectedResult {
  id: string;              // crypto.randomUUID()
  aim: string;
  description?: string;
  datasets?: string[];
  result: QueryResultState;
  created_at: number;      // Date.now()
}

interface OutputState {
  results: CollectedResult[];
  addResult: (r: Omit<CollectedResult, "id" | "created_at">) => void;
  removeResult: (id: string) => void;
  clearResults: () => void;
  syncToSession: () => Promise<void>; // persist to backend
}
```
- Generated with `create` from zustand, no persistence middleware (manual sync via `syncToSession`).
- `addResult` calls `syncToSession` after state update.
- `removeResult` and `clearResults` also call `syncToSession`.

### 3. `sessionStore.ts` — Add output results sync action
Add to `SessionState`:
```ts
setOutputResults: (results: any[]) => void;
updateOutputResults: (results: any[]) => Promise<void>;
```
- `setOutputResults` — local state setter for loaded results from bootstrap/switchSession.
- `updateOutputResults` — PATCH to backend `state: { output_results: [...] }`, then local update.

### 4. `ChatSection.tsx` — Changes
**a. Remove modal:** Delete lines 850–882 (`expandedAimResult` modal).

**b. Push results to outputStore on success:**
```ts
// In handleRunAimSql, after successful setAimResults:
import { useOutputStore } from "../stores/outputStore";
const outputStore = useOutputStore.getState();
outputStore.addResult({
  aim: aimDef.aim,
  description: aimDef.description,
  datasets: aimDef.datasets,
  result: { loading: false, ...res },
});
```

**c. Remove `expandedAimResult` state variable** (line 346) and all references.

**d. Aim chip button behavior:**
- If `aimResults[a.aim]` has data (rows/error) → show small checkmark badge (static indicator, no click action needed).
- If no result → show "▶ Run" button (unchanged).
- Optionally add a "scroll to OutputPanel" action if user clicks the badge — but plan says "no click action needed" for simplicity.

**e. Listen for outputStore deletions to sync `aimResults`:**
```ts
useEffect(() => {
  const unsub = useOutputStore.subscribe(
    (state) => state.results,
    (results) => {
      // Rebuild aimResults from results list
      const map: Record<string, QueryResultState> = {};
      for (const r of results) {
        map[r.aim] = r.result;
      }
      setAimResults(map);
    }
  );
  return unsub;
}, []);
```
This keeps aim chip buttons in sync when user deletes from OutputPanel.

**f. Import `useOutputStore` and extract `QueryActions` to its own file.**

### 5. Extract `QueryActions` to `src/sections/QueryActions.tsx`
Currently defined inline in ChatSection.tsx (lines 239–320). Move to a shared component so both ChatSection and OutputPanel can import it.

**Same interface:**
```ts
function QueryActions({ queryResult }: { queryResult?: QueryResultState })
```
- Reuses `ChartView` which is also currently inline. Either keep it in QueryActions.tsx or extract separately.

### 6. `OutputPanel.tsx` — Full rewrite (~150 lines)
**Empty state:**
- Same visual style as ChatSection empty state — icon + "Run an aim to see results here".

**Header:**
- "Analysis Results" title with count badge `({results.length})`
- "Clear all" button (calls `outputStore.clearResults()`)

**Results list (scrollable):**
- Each result as `resultCardClass` card:
  - **Collapsed (default):** Aim name, row count · relative timestamp, expand toggle, delete button
  - **Expanded:** Full `QueryActions` component (chart/table toggle, SQL details, data table)

**Card structure:**
```
┌──────────────────────────────────────┐
│ 🎯 Aim Name                    [×]  │
│ 124 rows · 2 min ago                │
│ [▶ Show Details / ▼ Hide Details]   │
│ ┌──────────────────────────────────┐ │
│ │ SQL: SELECT ...                  │ │
│ │ [Chart/Table toggle]             │ │
│ │ (full table or chart)            │ │
│ └──────────────────────────────────┘ │
└──────────────────────────────────────┘
```

**Relative time:** `formatDistanceToNow` from `date-fns` (or simple custom: `Math.floor((Date.now() - ts) / 60000)` + "min ago").

### 7. `App.tsx` — No changes needed
Grid layout already handles responsive stacking. OutputPanel is the 3rd column on desktop.

## Files to Modify
1. **New:** `frontend/src/stores/outputStore.ts` (~45 lines)
2. **Edit:** `frontend/src/stores/sessionStore.ts` — add `setOutputResults` / `updateOutputResults`
3. **New:** `frontend/src/sections/QueryActions.tsx` (~85 lines, extracted from ChatSection)
4. **Edit:** `frontend/src/sections/ChatSection.tsx` — remove modal, push to store, sync aim chips, remove `QueryActions` inline
5. **Rewrite:** `frontend/src/sections/OutputPanel.tsx` (~150 lines)

## Edge Cases
- **Deleting while ChatSection open:** `useOutputStore.subscribe` in ChatSection rebuilds `aimResults` so chip updates immediately.
- **Session switch:** `bootstrap`/`switchSession` load `state.output_results` into outputStore; ChatSection subscribes and syncs.
- **Duplicate aim runs:** Each run creates a new `CollectedResult` with unique `id` — timeline accumulates all runs.
- **Error results:** Stored in outputStore just like successful results; displayed in red via `QueryActions` error state.

## Validation
1. Run SQL for an aim → result appears in OutputPanel
2. Refresh page → results reappear (persisted to backend)
3. Delete result from OutputPanel → aim chip in ChatSection reverts to "▶ Run"
4. Clear all → OutputPanel empties, all chips revert to "▶ Run"
5. Switch session → OutputPanel loads new session's results

## Open Question (resolved by this plan)
> Should OutputPanel results persist to backend `state_json["output_results"]`?

**Recommended answer: Yes.** This aligns with the project's persistence objective and the existing `aimProposals` pattern. Without this, results would be lost on every page refresh, undermining the "timeline" concept.
