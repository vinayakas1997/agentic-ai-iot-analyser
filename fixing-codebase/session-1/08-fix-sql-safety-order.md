# Fix 8: Fix validate_sql_safety false LIMIT warning (LOW)

**Status:** DONE

## Bug Description
`criticize_sql` in `aims.py` called `validate_sql_safety(cleaned)` on the raw SQL **before** `validate_sql()` added `LIMIT 200`. So even though the LIMIT would be added at execution time, the critic flagged "Missing LIMIT clause" as a safety issue — a false positive.

## Root Cause
`criticize_sql` passed `cleaned` (raw SQL without LIMIT) to `validate_sql_safety`. The safety check flagged missing LIMIT, but `execute_sql()` would have added it via `validate_sql()`.

## Files Changed
| File | What changed |
|------|-------------|
| `backend/aims.py` | Added `validate_sql` import; in `criticize_sql`, call `validate_sql(cleaned)` first (adds LIMIT if missing) then pass that result to both `explain_sql` and `validate_sql_safety` |

## Verification
- [x] Python import syntax verified
- [x] Backend container rebuilt
