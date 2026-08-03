# 02 — Follow-up analysis reuses template data

## Problem

When the user attaches a template output card as an aim (the existing Add button → `selectedAims`)
and asks a follow-up question, the backend routes to FOCUS. But FOCUS can't see the template's
query results:

- `_build_previously_fetched_section` (`focus_agent.py:134-154`) only matches turns where
  `aim in t.aims`. Template turns have `aims: []` (`api.py` `_apply_template_turn`), so the
  section is empty and the agent re-runs SQL from scratch.
- `_run_recall_result` (`focus_agent.py:233-263`) matches by topic words / aim / dataset tags —
  not reliably by template name.

The gathered rows are stored in `chat_query_results` but effectively invisible to follow-ups.

## Design principle

The follow-up prompt only ever lists `(label, columns, row_count)`. Full rows are fetched on
demand via `recall_result`. We never embed `query_results` into any prompt (see
`03-prompt-token-budget.md`).

## Changes

### `backend/api.py`
- `MessageRequest`: add `template_name: str = ""`.
- `_handle_template`: accept `template_name`.
- `_apply_template_turn` (`api.py:2076-2131`): store on the turn entry:
  - `"template_name": template_name`
  - `"run_label": "<card name>"` (e.g. "01 · Daily report") — human label for matching.
- Template route (`api.py:2036-2046`): pass `req.template_name` through.

### `backend/focus_agent.py`
- `_build_previously_fetched_section`: for each attached aim, also match turns by their
  `template_name` (equal or substring of the attached aim label, so "01 · Daily report" matches
  a turn with `template_name: "Daily report"`). List `- "Daily report" (N rows: cols)`.
- `_run_recall_result`: also match template turns by `template_name` (add to the tag matching at
  `focus_agent.py:243-246`), so a reference like "the Daily report" can recall its rows.

## Behavior after the fix

1. Template run → turn stored with `template_name` + `run_label`; rows in `chat_query_results`.
2. User attaches the card as an aim → `selectedAims` gets `{ aim: "01 · Daily report", description: template_name, datasets }`.
3. User sends a follow-up → FOCUS.
4. `_build_previously_fetched_section` lists the template turn as already fetched.
5. FOCUS calls `recall_result("Daily report")` → returns the stored rows. No re-query.

## Notes
- Small, additive backend change: no new endpoints, no schema change.
- The template agent's own `_build_previous_section` (`template_agent.py:42-58`) already lets a
  second template run reuse earlier results; this fix gives FOCUS the same ability.
