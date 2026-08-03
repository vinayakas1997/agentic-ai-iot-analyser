# Fix 13 — Follow-up FOCUS reuses template query results

## Problem

Attaching a template output card as an aim → follow-up FOCUS couldn't see the template's rows.
`_build_previously_fetched_section` (`focus_agent.py:134-154`) only matched turns where
`aim in t.aims`, and template turns had `aims: []`. So the FOCUS agent re-ran SQL from
scratch, wasting the gathered data. `_run_recall_result` also didn't match template turns.

## Fix

- `api.py`:
  - `MessageRequest`: added `template_name: str = ""`.
  - `_handle_template`: accepts `template_name` and stores it on the turn entry.
  - Template route: passes `req.template_name` through.
- `focus_agent.py`:
  - `_build_previously_fetched_section`: for each attached aim, also matches template
    turns whose `template_name` is a substring of the aim label (so "01 · Daily report"
    matches a turn with `template_name: "Daily report"`).
  - `_run_recall_result`: also matches template turns by `template_name` substring.
- Frontend: template card `description` = template name only (short), never the report text.

## Files touched

- `backend/api.py`
- `backend/focus_agent.py`

## Test / verification

- `python3 -m py_compile` clean on `api.py`, `focus_agent.py`.
- Template turn stores `template_name: "Test Report"` in session state.
- Follow-up FOCUS with `attached_aims=["Test Report"]` routes correctly and queries the
  dataset via the normal FOCUS pipeline.
- Containers rebuilt without errors.
