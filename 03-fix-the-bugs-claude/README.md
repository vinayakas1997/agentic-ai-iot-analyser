# Bug list — 2026-08-03 review

Found while investigating why a template run against a personal (uploaded CSV)
dataset burned all 16 agent rounds and returned "no data" for
user_id=106761, session_id=c99346a6-8bd8-4e51-ba0a-05b25622c3c4, and why
personal datasets appear to "overflow" into the registry dataset list in the
frontend context panel.

Status legend: `not started` / `fix drafted` / `fix applied, needs test` / `verified fixed`.

| # | File | Severity | Status |
|---|------|----------|--------|
| 01 | [01-personal-dataset-status-reset-on-reupload.md](01-personal-dataset-status-reset-on-reupload.md) | High | fix applied, needs test |
| 02 | [02-template-route-missing-empty-dataset-guard.md](02-template-route-missing-empty-dataset-guard.md) | High | fix applied, needs test |
| 03 | [03-frontend-personal-registry-dataset-merge.md](03-frontend-personal-registry-dataset-merge.md) | High | fix applied, needs test |
| 04 | [04-switchsession-no-race-guard.md](04-switchsession-no-race-guard.md) | High | fix applied, needs test |
| 05 | [05-progress-poller-follows-live-sessionid.md](05-progress-poller-follows-live-sessionid.md) | High | fix applied, needs test |
| 06 | [06-outputpanel-stale-dataset-lookup.md](06-outputpanel-stale-dataset-lookup.md) | High | fix applied, needs test |
| 07 | [07-query-router-substring-name-match.md](07-query-router-substring-name-match.md) | Medium | fix applied, needs test |
| 08 | [08-execute-query-missing-ownership-check.md](08-execute-query-missing-ownership-check.md) | Medium | fix applied, needs test |
| 09 | [09-registry-admin-maintained-by-orphan.md](09-registry-admin-maintained-by-orphan.md) | Low | not started — needs a product decision, see file |
| 10 | [10-session-poller-clobbers-fresh-meta.md](10-session-poller-clobbers-fresh-meta.md) | Low | fix applied, needs test |

Fixes 01–08 and 10 are implemented (both backend Python and frontend
TypeScript changes have been verified to parse/typecheck cleanly:
`python3 -m py_compile` / `ast.parse` for backend files, `tsc --noEmit` for
frontend). None have been exercised against a running app/DB yet — see each
file's "Test plan" section for what to verify manually or in CI.

Bug 09 was intentionally left unfixed: `maintained_by` may be set to a
different user than the creator on purpose (e.g. an IoT admin assigning a
draft dataset to a specific maintainer), so forcing it to match `user_id`
could break an intended workflow. Needs a product decision before a fix is
written.
