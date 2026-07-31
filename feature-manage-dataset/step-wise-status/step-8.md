# Step 8 — Frontend: EN/JA translations

> Status: DONE

## What was done

In `frontend/src/lib/translations.ts`:
- Added EN keys for the new UI (registry-admin right-panel labels + a `conn.*` group for the
  connection panel: add-new, test, reachable/unreachable, latency, saved connections, etc.).
- Added matching JA translations for every new key.

New keys added (EN + JA):
`registryAdmin.connection`, `.selectConnection`, `.mainDb`, `.searchTables`, `.chooseTable`,
`.loadFrom`, `.startDate`, `.autoDetected` and `conn.title`, `.subtitle`, `.name`, `.dbType`,
`.host`, `.port`, `.database`, `.username`, `.password`, `.schema`, `.addTest`, `.saving`,
`.testing`, `.test`, `.reachable`, `.unreachable`, `.latency`, `.savedConnections`,
`.noConnections`, `.required`, `.invalidType`, `.testFailed`.

## Test results

- `tsc -p tsconfig.app.json --noEmit` → no new errors (translations file is string-keyed).
