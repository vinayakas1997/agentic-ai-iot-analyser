# Fix 5: Standardize table key naming (MEDIUM)

**Status:** DONE

## Bug Description
Dataset data dicts used inconsistent keys for the table name: `table_name` in `send_message` handler (api.py:934) vs `table` in `execute_query` handler (api.py:354) and `listDatasets` (api.py:538). The `_build_context` function only checked `table_name`, so when context was built from `execute_query`-sourced data, the wrong table name would appear.

## Root Cause
Two code paths built `datasets_data` dicts with different key names. The `_build_context` function was not resilient to this inconsistency.

## Files Changed
| File | What changed |
|------|-------------|
| `backend/api.py:562` | `_build_context` now checks `table_name` or `table` or falls back to `dataset_name` |
| `backend/api.py:934` | Changed `table_name` to `table` for consistency with other code paths |

## What Was Done
1. Updated `_build_context` to use `ds.get("table_name") or ds.get("table") or ds.get("dataset_name", "?")` — safe fallback chain
2. Changed `table_name` key to `table` in `send_message` handler to match the convention used everywhere else

## Verification
- [x] Syntax check passed
- [x] Backend container rebuilt and restarted

## Notes
The `table` key is now used consistently across all three data-building locations (execute_query, listDatasets, send_message), and `_build_context` is resilient to either key.
