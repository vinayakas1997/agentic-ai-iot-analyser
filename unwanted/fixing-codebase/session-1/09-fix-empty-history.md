# Fix 9: Frontend sends empty history, backend had no fallback (LOW)

**Status:** DONE

## Bug Description
The frontend hardcoded `history: []` when calling `sendMessage` (sessionStore.ts line 310). The backend RESEARCH-mode route handlers (`_handle_direct`, `_handle_suggest`, etc.) didn't receive or use history at all — they relied solely on `enrichment_block`, which only included turns matching attached aims/datasets tags. On the first message or when no tags matched, the LLM got no conversation context.

## Solution
1. Added `build_conversation_history()` helper that extracts the last N turns from stored session state
2. Appended conversation history to the enrichment block for both RESEARCH mode and SUMMARY mode, ensuring the LLM always sees recent conversation turns

## Files Changed
| File | What changed |
|------|-------------|
| `backend/api.py` | Added `build_conversation_history()` function; appended conv_history to enrichment_block in both RESEARCH and SUMMARY code paths |

## Verification
- [x] Python import syntax verified
- [x] Backend container rebuilt
