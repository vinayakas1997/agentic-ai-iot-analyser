# Fix 12 — Template output cards in the OutputPanel

## Problem

Template runs produced a report + `query_results` but appeared only inside the chat turn bubble.
OutputPanel cards were aim-only — `useOutputStore.addResult` was only called for FOCUS /
multi-aim FOCUS / proposals. Users couldn't see or count how many times they ran a template,
and the result wasn't attachable for follow-up analysis.

## Fix

- Extended `CollectedResult` in `outputStore.ts` with optional `kind`, `template_name`, `report`, `queryResults`.
- `ChatSection.tsx` `handleSend`: added a template branch that captures the template name, computes a per-template run counter (`"01 · Daily report"`, `"02 · Daily report"`), and calls `useOutputStore.addResult(...)` with the report text, query results, and datasets.
- `OutputPanel.tsx`: renders a "Template" badge + report markdown + all query results tables for template cards.
- `client.ts` `sendMessage`: accepts `templateName` → `body.template_name` so the backend can label the turn.
- `sessionStore.ts`: `sendUserMessage` + its type signature forward `templateName`.
- `translations.ts`: EN + JA keys `output.templateBadge`, `output.templateReport`.

## Files touched

- `frontend/src/stores/outputStore.ts`
- `frontend/src/sections/ChatSection.tsx`
- `frontend/src/sections/OutputPanel.tsx`
- `frontend/src/api/client.ts`
- `frontend/src/stores/sessionStore.ts`
- `frontend/src/lib/translations.ts`

## Test / verification

- `npx tsc -p tsconfig.app.json --noEmit` clean (0 errors).
- `vite build` succeeds.
- Template API call → `route: "template"`, `query_results` returned.
- Template turn stores `template_name: "Test Report"` in session state.
