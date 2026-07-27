# Fix 14: Update stale "empty history" comment (LOW)

**Status:** DONE

## Bug Description
Comment at `sessionStore.ts:297` said "Send empty history — enrichment block replaces it" which was from before Fix 9. History is now built from stored turns, not just enrichment.

## Files Changed
| File | Change |
|------|--------|
| `stores/sessionStore.ts:297` | Updated comment to "History built server-side from stored turns (via enrichment block + conv history)" |

## Verification
- [x] Frontend builds without errors
