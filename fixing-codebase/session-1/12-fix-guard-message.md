# Fix 12: Fix misleading guard message when aims attached without datasets (LOW)

**Status:** DONE

## Bug Description
Second guard in `send_message` (api.py:919) fired when `dataset_names` was empty but `attached_aims` was populated. The message only said "select at least one dataset" — ignoring that the user had already attached aims.

## Files Changed
| File | Change |
|------|--------|
| `backend/api.py:922` | Updated message to acknowledge attached aims: "(Aims are attached but need datasets to execute.)" |

## Verification
- [x] Backend container rebuilt
