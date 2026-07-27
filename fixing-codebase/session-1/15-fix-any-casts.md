# Fix 15: Remove unnecessary `as any` TypeScript casts (LOW)

**Status:** DONE

## Bug Description
`sessionsStore.ts` had 3 `as any` casts:
1. `(s as any).mode` in refreshSessions — type didn't include `mode` field
2. `(detail as any).mode` in bootstrap — same
3. `(t: any)` in turns mapping — API turn type didn't include `aims`, `datasets`, `analysis_actions`, `result_uuid`

## Files Changed
| File | Change |
|------|--------|
| `api/client.ts:89,96-102` | Added `mode?: string` to `listSessions` and `getSession` return types; added `aims?`, `datasets?`, `analysis_actions?`, `result_uuid?` to turn type |
| `stores/sessionStore.ts:112` | Removed `as any` from `s.mode` |
| `stores/sessionStore.ts:123` | Removed `as any` from `detail.mode` |
| `stores/sessionStore.ts:124` | Removed `(t: any)` cast — now properly typed via client.ts return type |

## Verification
- [x] Frontend builds without errors
