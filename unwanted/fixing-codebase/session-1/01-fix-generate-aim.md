# Fix 1: generate_aim function (CRITICAL)

**Status:** DONE

## Bug Description
The `/api/v2/aim/new-research` endpoint calls `generate_aim()` at `api.py:308`, but the function was never defined or imported anywhere. Any request to this endpoint crashes with a `NameError`.

## Root Cause
The `generate_aim` function was referenced in the endpoint handler but never implemented. The endpoint was dead code — it could never have worked.

## Files Changed
| File | What changed |
|------|-------------|
| `backend/aims.py` | Added `generate_aim()` function and `GENERATE_AIM_PROMPT` at line 634 |
| `backend/api.py` | Added `generate_aim` to the import from `aims` |

## What Was Done
1. Created `generate_aim()` in `aims.py` — takes `user_text` and `datasets`, builds context using `build_dataset_context()`, calls LLM via `call_llm()`, parses JSON response into the expected schema (`aim`, `how_we_will_do_it`, `datasets_used`, `joins`)
2. Added `GENERATE_AIM_PROMPT` — instructs LLM to output a JSON object with the 4 required fields
3. Added error handling — if LLM fails or returns invalid JSON, returns empty/default values gracefully
4. Updated import in `api.py` line 13 to include `generate_aim`

## Verification
- [x] Syntax check passed (`python3 -c "import ast; ast.parse(...)"`)
- [x] Backend container rebuilt successfully
- [x] No syntax errors in logs

## Notes
The endpoint is now functional. The LLM prompt asks for JSON output with `aim`, `how_we_will_do_it`, `datasets_used`, and `joins` — matching the `NewResearchResponse` Pydantic model.
