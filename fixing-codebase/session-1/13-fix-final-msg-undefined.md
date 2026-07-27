# Fix 13: Initialize `final_msg` to prevent undefined risk (MEDIUM)

**Status:** DONE

## Bug Description
`_handle_deep` used `final_msg if 'final_msg' in locals() else raw` — a fragile pattern. While the loop always sets `final_msg` on the last iteration, any future code path change could leave it undefined.

## Files Changed
| File | Change |
|------|--------|
| `backend/api.py:807` | Initialize `final_msg = ""` before loop |
| `backend/api.py:886` | Replace `locals()` check with simple `final_msg or raw` |

## Verification
- [x] Backend container rebuilt
