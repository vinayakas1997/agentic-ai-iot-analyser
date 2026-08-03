# 08 — `/execute-query` endpoint has no session-ownership check

**Severity:** Medium
**Status:** fix applied, needs test

## Explanation

`agentic-project/backend/api.py`, `execute_query` (lines 692-703), accepts
a `session_id` in the request but never loads the corresponding
`ManagerSession` row or verifies the caller owns it. Every other endpoint
that accepts `session_id` performs an ownership check — e.g.
`bucket_proceed` (lines ~672-678) and `send_message` (lines ~1980-1982) both
verify `session.user_id == uid` (via `_get_session_owned` or an inline
check) before proceeding.

`execute_query` instead scopes personal datasets directly to
`req.user_id` and just echoes `req.session_id` back in the response without
reading session state from it. Today this is not an exploitable data leak
in practice — registry datasets are effectively public and personal ones
are already scoped by the caller-supplied `user_id` — but it is an
inconsistency with the "always verify ownership for session-bearing
endpoints" pattern followed everywhere else, and would become a real gap if
this endpoint is ever extended to read or write session state (a plausible
next step, mirroring how `/messages` evolved).

## Files touched (to fix)

- `agentic-project/backend/api.py` (`execute_query`, lines 692-703)
  - Add the same ownership check used by other session-bearing endpoints
    (`_get_session_owned` or equivalent `session.user_id != uid` check)
    before proceeding, for consistency and to close the gap before this
    endpoint is extended further.

## Test plan

1. Confirm current behavior: call `/execute-query` with a `session_id`
   belonging to a different user than `req.user_id` and observe it succeeds
   today (documents the current gap).
2. Apply the ownership check fix.
3. Re-run the same call and confirm it now returns 403 (matching the
   behavior of `/messages` and other session-bearing endpoints for
   cross-user session_id/user_id combinations).
4. Regression: confirm the endpoint still works normally when
   `session_id` and `user_id` are correctly paired.

## Current status

Fix applied in `agentic-project/backend/api.py`, `execute_query`: added the
same ownership check pattern used by `bucket_proceed` — loads the
`ManagerSession` row for `req.session_id` and raises 404 if missing / 403 if
`session.user_id != uid` — before proceeding to dataset resolution.
`python3 -m ast.parse` confirms the file still parses. Needs the manual
test plan above (call with a `session_id` owned by a different user)
executed against a running backend.
