# 11 — Successful template runs never created an OutputPanel card (dead-code condition ordering)

**Severity:** High (regression from the 16-round fix)
**Status:** fix applied
**Repro:** user_id=106761, session a72b9010-2342-4ffb-a390-8525cfbbfd81 ("Run template report" on 生産情報_2026_07_10) and session 25191265-71f3-44e3-94b4-d660270de4d8

## Explanation

`agentic-project/frontend/src/sections/ChatSection.tsx`, `handleSend`:

```ts
if (res?.result_uuid && res?.query_result) {        // ← template responses match this FIRST
  ...
  if (aimNames.length > 0) {                        // ← template runs have no aims → false
    useOutputStore.addResult(...); persistTurns();  //    nothing happens
  }
} else if (res?.deep_iterations?.length) { ... }
} else if (res?.route === "template") {             // ← UNREACHABLE for successful templates
  // create template card + persist output_results
}
```

A **successful** template response always includes `result_uuid` + `query_result`
(`_handle_template` in `api.py` sets both), so the first branch always wins and the
`route === "template"` branch is never reached. Because a template run has no
selected aims, `aimNames.length === 0` and the first branch does nothing visible:
**no OutputPanel card is created and `output_results` is never written to the
session state.**

Ironic twist: the template-card branch only ever executed for **truncated** runs
(result_uuid/query_result null → falls through). So cards worked during the earlier
16-round failures and broke the moment templates started succeeding (see bug 02 / 07).

## Fix

- `ChatSection.tsx`: reordered the response handling so `res?.route === "template"`
  is checked **first** — a template run now always calls `addResult({kind:"template",
  ...})` + `persistTurns()`, writing `output_results` to session state.
- `sessionStore.ts`: added `reconstructTemplateCards(rawTurns, existingResults)` and
  wired it into `bootstrap()` and `switchSession()`. On session load it rebuilds a
  card for every stored template turn (`route==="template"` / `template_name`) that
  has no matching card yet, from the turn's own `template_name`, `agent_message`,
  `query_result` and `query_results`. This also recovers runs made before the fix
  (e.g. session a72b9010-…, whose turn already contains everything needed).
- `types/manager.ts`: `Turn` gained optional `template_name` and `route` fields.

## Verification

- `tsc --noEmit -p tsconfig.app.json` passes; frontend container rebuilt.
- The stored turn for a72b9010-… has `route=template`, `template_name=hourly
  analysis`, `query_result` (5 rows), `query_results` (2), `agent` (1486 chars) —
  reloading that session now reconstructs the "01 · hourly analysis" card.
- Manual check: hard-refresh the browser, open the session, confirm the card
  appears in the OutputPanel, and re-running the template stacks a "02 · …" card.

## Note

Cards are still a browser-side artifact: they are created by `handleSend` and
persisted as `session_state.output_results` by the frontend's `persistTurns()`
(backend `_handle_template` does not write `output_results`). Template runs made
outside the browser are now covered on reload by `reconstructTemplateCards`.
