# 02 — Template route runs the full 16-round agent loop even when no datasets resolved

**Severity:** High
**Status:** fix applied, needs test
**Directly explains:** the reported symptom — template + personal dataset uses all 16 rounds and says "no data"

## Explanation

In `agentic-project/backend/api.py`, the "unresolved dataset name" guard
(around lines 2034–2042) only short-circuits the request when
`req.enrichment_mode == "research"`:

```python
if unresolved:
    logger.warning(...)
    if not datasets_data and req.enrichment_mode == "research":
        return MessageResponse(..., agent_message=f"No datasets found for: ...")
```

The TEMPLATE branch, triggered right after at line 2046
(`if req.format_spec.strip():`), has no equivalent check. It calls
`_handle_template(...)` (line ~2048) unconditionally, even when
`datasets_data` is `[]`.

`_handle_template` (`api.py:1897-1936`) then calls `run_template_agent`
(`agentic-project/backend/template_agent.py`) with an empty dataset list.
The template agent's system prompt (`template_agent.py:61-108`) instructs it
to treat SQL errors as a retry signal, never as an answer (line ~89), so it
keeps calling `query_data` per report field against tables that don't
exist, retrying each failure, until `template_max_rounds` (16,
`config.py:25`) is exhausted and it force-answers "no data" for every field
(`template_agent.py:161-169`, `stopped_reason: "budget"`).

This is the direct mechanical cause of the reported failure. Bug 01 (or a
plain name/status mismatch) is the likely reason `datasets_data` ended up
empty in the first place for session c99346a6-8bd8-4e51-ba0a-05b25622c3c4;
this bug is why the system didn't fail fast and clearly when that happened.

## Files touched (to fix)

- `agentic-project/backend/api.py`
  - Around line 2046, before entering the template branch, add a check:
    if `not datasets_data` (or `unresolved` is non-empty and covers all
    requested datasets), return a direct `MessageResponse` explaining which
    dataset(s) failed to resolve — mirroring the research-mode guard at
    lines 2037-2042 — instead of calling `_handle_template`.

## Test plan

1. Attach a dataset name that does not resolve (deleted, wrong status, typo)
   to a session with a saved template.
2. Send the template request.
   - **Before fix:** request takes ~16 rounds worth of LLM calls, several
     seconds/minutes, ends with "no data" for every report field.
   - **After fix:** request returns immediately with a clear
     "dataset not found / not active" message, no wasted LLM rounds.
3. Regression check: attach a valid, resolving dataset and confirm the
   template route still executes normally and produces a real report.
4. Add an automated test (if a test suite exists for `api.py`'s message
   endpoint) asserting `_handle_template` is never invoked when
   `datasets_data` is empty for the template branch.

## Current status

Fix applied in `agentic-project/backend/api.py`, right before the
`if req.format_spec.strip():` template dispatch: added `if not
datasets_data:` returning a direct `MessageResponse` (including the
unresolved dataset names, if any) instead of calling `_handle_template`.
Needs the manual test plan above executed against a running backend.
