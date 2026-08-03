# 09 — Registry draft entries can be orphaned via a mismatched `maintained_by`

**Severity:** Low
**Status:** not started (lower-confidence, not fully verified as reproducible)

## Explanation

`agentic-project/backend/api.py`, `create_draft_entry` (lines ~1240-1275),
accepts `maintained_by` as a free-text field on the request, independent of
`req.user_id`. Meanwhile `confirm_entry` and `delete_entry` in
`agentic-project/backend/registry_admin.py` (lines 133 and 180
respectively) gate the operation on `row.maintained_by != user_id`.

If a caller supplies a `maintained_by` value at creation time that doesn't
match their own `user_id` (accidentally or otherwise), the resulting draft
row can never be confirmed or deleted by that same user afterward — it
becomes an orphaned draft with no path to be resolved except direct DB
intervention.

This is flagged for awareness rather than as a confirmed active bug in
production, since it requires a specific input mismatch to trigger and no
reproduction was attempted against live data.

## Files touched (to investigate/fix)

- `agentic-project/backend/api.py` (`create_draft_entry`, ~lines 1240-1275)
  - Consider deriving `maintained_by` from the authenticated `user_id`
    rather than accepting it as independent free text, or validate that it
    matches `req.user_id` at creation time.
- `agentic-project/backend/registry_admin.py` (`confirm_entry` line ~133,
  `delete_entry` line ~180)
  - Alternatively, allow an admin/override path to reassign or resolve
    orphaned drafts.

## Test plan

1. Call the draft-creation endpoint with `maintained_by` set to a value
   different from `req.user_id`.
2. As the same user (`req.user_id`), attempt to confirm or delete that
   draft.
   - **Before fix:** operation is rejected (`maintained_by != user_id`),
     with no way for the creating user to resolve it.
   - **After fix:** either the mismatch is prevented at creation time, or
     there's a clear path to resolve/reassign the orphaned draft.

## Current status

Not started — intentionally left unfixed. Confirmed via
`agentic-project/backend/api.py:1250-1275` (`registry_create_entry`) that
`maintained_by` is taken directly from `req.maintained_by`, independent of
`req.user_id`. This could be by design (an IoT admin assigning a draft to a
specific team member as maintainer), so forcing it to equal `user_id` risks
breaking an intended workflow. Needs a product decision — confirm with
whoever owns the registry-admin feature whether `maintained_by` should ever
differ from the creator, before writing a fix here.
