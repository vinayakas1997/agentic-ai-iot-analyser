# 03 — Prompt token budget + compaction

## Problem

There is **no overall token budget** across the composed system prompt. What exists today is
piecewise and insufficient:

- `build_enrichment_block` (`api.py:451-529`) caps at 4000 tokens (uses `estimate_tokens`).
- `build_conversation_history` (`api.py:532-541`) is appended **after** the enrichment cap,
  uncapped (last 5 turns, 200 chars each).
- `aims.py:326-332` truncates history entries > 1000 chars, but only on the non-enrichment path.
- Attaching several aims (or a long report as an aim description) can silently exceed the
  model's context window.
- No compaction priority when the budget is hit — oldest content should go first.

## Design principle (agreed with user)

Enrich only the explanation (agent message), dataset names, and the SQL query. Rows are fetched
on demand via `recall_result`. Keep aim descriptions short (template name only, never the report
text). Budget the whole prompt; compact oldest-first when over budget.

## Changes

### `backend/api.py`
- Add a reusable helper that assembles the full FOCUS/DIRECT system prompt under one
  `estimate_tokens`-based budget:
  - inputs: context, enrichment block, previously-fetched section, conversation history, aims/descriptions
  - budget: new setting `PROMPT_MAX_TOKENS` (default ~6000; output budget is `settings.max_tokens` = 4096)
  - assemble in priority order; while over budget, drop:
    1. oldest conversation-history turns
    2. oldest previously-fetched entries
    3. oldest enrichment summaries (existing `build_enrichment_block` cap becomes one layer; the
       new helper is the outer layer)
- Wire the helper into the FOCUS handler (`_handle_focus`) and DIRECT handler (`_handle_direct`).
- Log the estimated prompt tokens (debug) so the budget is verifiable.

### Keep the frontend small
- Template card `description` = template name only (not the report) so the "Active research
  aims:" line in `_build_context` (`api.py:1388-1395`) stays tiny.
- `_build_context` for FOCUS already runs with `include_samples=False` — keep it that way.

## Notes
- Pure addition: existing prompts keep working, now bounded.
- `estimate_tokens` is ~4 chars/token (`api.py:446-448`) — consistent with the existing code.
