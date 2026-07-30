# Fix 11: Replace silent error swallowing with console.error (MEDIUM)

**Status:** DONE

## Bug Description
6 locations used `.catch(() => {})` which silently dropped API errors — users would never know if data persistence or fetching failed.

## Files Changed
| File | Line | Change |
|------|------|--------|
| `stores/sessionStore.ts:293` | `updateSessionState` → `.catch(console.error)` |
| `stores/sessionStore.ts:326` | `updateSessionTitle` → `.catch(console.error)` |
| `stores/sessionStore.ts:340` | `updateSessionState` chat_query_results → `.catch(console.error)` |
| `sections/ChatSection.tsx:84` | `listDatasets` → `.catch(console.error)` |
| `sections/ChatSection.tsx:399` | `updateSessionState` selected_aims → `.catch(console.error)` |
| `sections/ContextSection.tsx:34` | `listDatasets` → `.catch(console.error)` |

## Verification
- [x] Frontend builds without errors
