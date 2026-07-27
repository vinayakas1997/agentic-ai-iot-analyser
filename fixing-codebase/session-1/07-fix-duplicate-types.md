# Fix 7: Remove duplicate type definitions (LOW)

**Status:** DONE

## Bug Description
`ChartConfig`, `ChartSuggestions`, and `DatasetInfo` were defined in multiple files with identical (ChartConfig/Suggestions) or slightly different (DatasetInfo) shapes. The `DatasetInfo` in `types/index.ts` was unused and had a different shape from the 3 identical local definitions in `ChatSection.tsx`, `ContextSection.tsx`, and `PreviewModal.tsx`.

## Files Changed
| File | What changed |
|------|-------------|
| `frontend/src/types/manager.ts` | Removed unused `ChartConfig`, `ChartSuggestions` exports (lines 148–161) — the kept ones in `sections/QueryActions.tsx` are what's imported |
| `frontend/src/types/index.ts` | Replaced dead `DatasetInfo` shape with the common one used across 3 consumer files |
| `frontend/src/sections/ChatSection.tsx` | Removed local `DatasetInfo` interface, added `import type { DatasetInfo }` |
| `frontend/src/sections/ContextSection.tsx` | Same |
| `frontend/src/components/PreviewModal.tsx` | Same |

## Verification
- [x] Frontend builds without errors
