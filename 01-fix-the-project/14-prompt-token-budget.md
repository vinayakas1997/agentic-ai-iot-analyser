# Fix 14 — Overall prompt token budget + compaction

## Problem

There was no overall token budget across the composed system prompt. Existing piecewise
caps (4000-token enrichment block, 200-char truncations) were insufficient: conversation
history was appended uncapped, and multiple attached aims (or long descriptions) could
silently exceed the model context window.

## Fix

- `config.py`: added `prompt_max_tokens: int = 6000` (env-var overridable via
  `PROMPT_MAX_TOKENS`).
- `api.py`:
  - Added `trim_text_to_budget(text, max_tokens)` helper: drops oldest lines from text
    until it fits within the budget.
  - Wired it into `send_message` after `build_enrichment_block` + `build_conversation_history`
    are combined, so the full enrichment block (summaries + conversation history) stays
    under the budget without silently exceeding the context.
- Frontend: template card `description` kept short (template name only) so `aim_descriptions`
  don't bloat `_build_context`'s "Active research aims:" line.

## Files touched

- `backend/config.py`
- `backend/api.py`

## Test / verification

- `python3 -m py_compile` clean on `config.py`, `api.py`.
- `prompt_max_tokens=6000` confirmed via config readout.
- Template `description` = template name (short) confirmed in the frontend — no report
  text flows into aim_descriptions.
