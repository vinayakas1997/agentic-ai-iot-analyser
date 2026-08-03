# 03 — Personal datasets merged into the same untagged list as registry datasets (the "overflow" bug)

**Severity:** High
**Status:** fix applied, needs test
**Directly explains:** "why does the personal dataset overflow into the dataset [search] list"

## Explanation

`agentic-project/frontend/src/sections/ChatSection.tsx`, lines 109-129 —
the effect that builds the dataset **search bar** list does:

```ts
Promise.all([listDatasets(), listUserDatasets(uid)]).then(([globalDs, personalRes]) => {
  const personalDs: DatasetInfo[] = (personalRes.datasets || [])
    .filter((d) => d.status === "active")
    .map((d) => ({ dataset_name: d.dataset_name, ... }));
  setDatasets([...globalDs, ...personalDs]);   // merged into ONE array
})
```

Both registry datasets and personal (uploaded CSV) datasets end up in the
same `datasets` state with no `source`/`kind` field to distinguish them.
This `datasets` array backs the registry search dropdown
(`ChatSection.tsx:138-148` `filtered`, rendered ~lines 713-760), so personal
datasets appear as ordinary search results there.

When picked from search, the name lands in the shared
`useDatasetStore.selected` array (no origin tag either). In
`agentic-project/frontend/src/sections/ContextSection.tsx`
(`datasetLookup` at lines 119-140), this shared selection is rendered in the
top "Datasets" (registry) box (lines 213-284) — even for entries that are
actually personal datasets — while the same dataset also legitimately
appears in the dedicated "Personal Datasets" box (lines 286-366), since that
section independently re-fetches personal datasets. Net result: a personal
dataset visually shows up in both the "Datasets" box and the "Personal
Datasets" box — the reported "overflow."

The same merge-without-tag pattern is repeated in
`agentic-project/frontend/src/sections/OutputPanel.tsx` (lines 50-71),
where personal entries are only added `if (!map.has(...))` — so if a
personal dataset happens to share a name with a registry dataset, the
registry entry silently wins everywhere lookups are used (columns shown,
"in use" toggles, deletion checks), see bug 08 in `06-outputpanel-...` file
for the related staleness issue.

## Files touched (to fix)

- `agentic-project/frontend/src/sections/ChatSection.tsx` (lines ~109-129)
  - Do not concatenate `personalDs` into the same `datasets` array used for
    the registry search dropdown. Keep the search bar registry-only
    (`listDatasets()` alone).
  - If personal datasets should also be attachable via the same search UI,
    tag every dataset object with `source: "registry" | "personal"` so
    downstream consumers can filter/render distinctly instead of merging
    blindly.
- `agentic-project/frontend/src/sections/ContextSection.tsx` (lines ~119-145,
  213-366)
  - Use the `source` tag to ensure the "Datasets" box only shows
    registry-sourced selections and "Personal Datasets" only shows
    personal-sourced ones — no dataset should be able to render in both.
- `agentic-project/frontend/src/sections/OutputPanel.tsx` (lines ~50-71)
  - Same tagging fix for `datasetLookup` construction, so a name collision
    between a personal and registry dataset doesn't silently prefer one over
    the other without indication.
- Possibly `agentic-project/frontend/src/stores/datasetStore.ts` — add the
  `source` field to whatever shape is stored in `selected`.

## Test plan

1. Create a personal (uploaded CSV) dataset named e.g. `sensor_data`.
2. Open the context panel and use the dataset search bar.
   - **Before fix:** `sensor_data` appears in the registry search results,
     indistinguishable from a real registry dataset.
   - **After fix:** search bar only shows registry datasets (or personal
     ones are visibly tagged as personal).
3. Attach `sensor_data` via the search bar (or via the personal upload
   flow) and observe the context panel.
   - **Before fix:** dataset appears in both "Datasets" and
     "Personal Datasets" boxes.
   - **After fix:** dataset appears exactly once, in the correct box.
4. Create a registry dataset and a personal dataset with the *same* name;
   verify column/lookup info shown reflects the correct source rather than
   silently preferring the registry entry.
5. Manual UI test in browser (dev server) covering upload → search → attach
   → view in context panel, for both light and dark theme if applicable.

## Current status

Fix applied:
- `DatasetInfo` (`agentic-project/frontend/src/types/index.ts`) gained an
  optional `source?: "registry" | "personal"` field.
- `ChatSection.tsx`: registry and personal datasets are now tagged with
  `source` when fetched; a new `searchableDatasets` memo filters out
  `source === "personal"` before feeding the search dropdown, so personal
  datasets no longer appear as registry search results.
- `ContextSection.tsx`: `datasets`/`datasetLookup` entries are tagged with
  `source`; `selectedDatasetInfos` (used by the "Datasets" box) now
  excludes `source === "personal"` entries, so a personal dataset can no
  longer render in both the "Datasets" and "Personal Datasets" boxes. The
  box's item count now uses `selectedDatasetInfos.length` instead of the
  unfiltered `storeSelected.length`.
- `OutputPanel.tsx`: same `source` tagging applied to its own
  `datasetLookup` for consistency (see also bug 06 in this same file).

`tsc --noEmit` passes. Needs the manual browser test plan above (upload →
search → attach → view in context panel) executed against the running dev
server.
