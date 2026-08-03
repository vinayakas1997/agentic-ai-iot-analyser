# 06 — `OutputPanel.tsx` dataset lookup never refreshes after a CSV upload

**Severity:** High
**Status:** fix applied, needs test

## Explanation

`agentic-project/frontend/src/sections/OutputPanel.tsx`, lines 82-91: the
effect that builds the dataset lookup used for validating which datasets
are available runs with an empty dependency array (`[]`), i.e. only once on
mount.

By contrast, the equivalent effects in
`agentic-project/frontend/src/sections/ChatSection.tsx` (lines 109-129) and
`agentic-project/frontend/src/sections/ContextSection.tsx` (lines ~47-56)
both re-run whenever `personalDatasetsVersion` changes — i.e. right after a
new CSV is uploaded.

**Failure scenario:** user uploads a new personal CSV mid-session (after the
app already loaded), then goes to `OutputPanel` and clicks "Run" on a
proposed aim, or "Summarize," that references the newly uploaded dataset.
`filterAvailable()` (lines ~73-80, used at 97-98 and 111) checks the new
dataset against the stale `datasetLookup` built at mount time, treats it as
"missing," logs a warning, and silently skips it from the request — the
user sees the action run without the dataset they just uploaded, with no
clear explanation why.

## Files touched (to fix)

- `agentic-project/frontend/src/sections/OutputPanel.tsx` (lines ~82-91)
  - Add `personalDatasetsVersion` (or whatever equivalent trigger
    `ChatSection.tsx`/`ContextSection.tsx` use) to the effect's dependency
    array so the lookup refreshes after uploads, matching the pattern used
    elsewhere.

## Test plan

1. Load the app, open a session, go to `OutputPanel`.
2. Upload a new personal CSV dataset from elsewhere in the UI (e.g. via the
   upload flow in `ContextSection`/`ChatSection`).
3. Without reloading the page, attach/reference the new dataset in an aim
   or summary action from `OutputPanel` and run it.
   - **Before fix:** dataset is silently treated as missing/unavailable;
     action runs without it (or fails with a "missing dataset" message even
     though it was just uploaded).
   - **After fix:** dataset is recognized immediately and included in the
     action.
4. Confirm no regression: existing datasets present at mount time still
   resolve correctly.

## Current status

Fix applied in `agentic-project/frontend/src/sections/OutputPanel.tsx`:
added `const personalDatasetsVersion = useUploadStore((s) =>
s.personalDatasetsVersion);` and added it to the dataset-fetch effect's
dependency array (previously `[]`), matching the pattern already used in
`ChatSection.tsx`/`ContextSection.tsx`. Also tagged the personal-dataset
branch of `datasetLookup` with `source: "personal"` while touching this
file (see bug 03). `tsc --noEmit` passes. Needs the manual test plan above
(upload a CSV mid-session, then run an aim/summary referencing it from
`OutputPanel` without reloading) executed in the browser.
