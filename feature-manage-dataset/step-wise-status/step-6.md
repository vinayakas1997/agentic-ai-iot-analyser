# Step 6 — Frontend: API client functions + types

> Status: DONE

## What was done

In `frontend/src/api/client.ts`:
- New `DbConnection` type and `ConnectionTestResult` type.
- New functions: `createDbConnection`, `listDbConnections`, `deleteDbConnection`,
  `testDbConnection`, `listConnectionTables`.
- New `IntrospectResult` type (adds `data_earliest_ts`, `data_earliest_col`) and
  `introspectTable(tableName, userId?, connectionId?)` — passes `connection_id` when present.
- `createRegistryEntry` extended with `connection_id` and `data_earliest_ts`.
- `RegistryEntry` extended with `connection_id`, `db_type`, `data_earliest_ts`.

## Test results

- `tsc -p tsconfig.app.json --noEmit` → **no errors in client.ts** (only pre-existing errors in
  unrelated files AppTour.tsx / TourDemoCharts.tsx / QueryActions.tsx).
