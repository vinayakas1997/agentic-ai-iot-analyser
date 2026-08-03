# 01 — Template output cards in the OutputPanel

## Problem

Template runs produce a report + `query_results`, but only appear inside the chat turn bubble.
OutputPanel cards are aim-only (`useOutputStore.addResult` is only called for FOCUS / multi-aim
FOCUS / proposals). Users can't see or count how many times they ran a template, and the result
isn't attachable for follow-up analysis.

## Changes

### `frontend/src/stores/outputStore.ts`
Extend `CollectedResult` with optional fields so template cards are distinguishable and survive
reload (cards already persist via `persistTurns()` → `state.output_results`):

- `kind?: "aim" | "template"` (default "aim")
- `template_name?: string` (raw template name, for the counter + badge)
- `report?: string` (full report markdown)
- `queryResults?: QueryResultState[]` (all query tables from the run)

### `frontend/src/sections/ChatSection.tsx` — `handleSend`
- Capture the template name before it's cleared (line ~459):
  `const appliedTemplateName = appliedTemplate?.template_name;`
- Add a branch: `if (res.route === "template")`.
  - Run number = count of existing `outputResults` with the same `template_name` + 1.
  - Card name: `` `${String(n).padStart(2, "0")} · ${template_name}` `` → "01 · Daily report",
    "02 · Daily report" (per-template counter, unique per run so `outputStore` dedupe by exact
    `aim` never collapses them).
  - `description` = template name only (short — see `03-prompt-token-budget.md`).
  - `report` = `res.agent_message` (the full report text).
  - `result` = `res.query_result` (fallback `{ loading: false }` when no query ran).
  - `queryResults` = `res.query_results`.
  - `datasets` = attached dataset names; `kind: "template"`; `template_name`.
  - `useOutputStore.addResult(...)`.
- Works even when the run produced no queries (card still shows the report).

### `frontend/src/api/client.ts` — `sendMessage`
- Accept `templateName` and send `body.template_name` so the backend can label the turn
  (needed for `02-template-followup-reuse.md`).

### `frontend/src/sections/OutputPanel.tsx`
- When `r.kind === "template"`:
  - Show a "Template" badge (new translation key `output.templateBadge`) + template name near
    the title.
  - Render `r.report` as markdown in the card body.
  - Render every `queryResults` entry as its own `QueryActions`, falling back to the single
    `r.result`.
- The existing **Add** button stays untouched — it already attaches any card as an aim
  (`aim = card name`, `description = template name`, `datasets`).

### `frontend/src/lib/translations.ts`
- Add EN + JA keys: `output.templateBadge`.

## Notes
- No backend change is required for card creation itself (persistence is client-side via
  `output_results`). Backend change for the turn label is in doc 02.
- Cards are keyed by exact `aim`; numbered names guarantee one card per run.
