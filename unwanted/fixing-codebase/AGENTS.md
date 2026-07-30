# AGENTS.md — Self-Documenting Bug Fix Workflow

## Purpose

Automatically structured session tracking for every bug-fixing session. When told to fix bugs in the project, the agent creates numbered session folders, documents each fix attempt with root cause analysis, and records verification results — producing a complete audit trail.

---

## How to Start a Fix Session

1. List existing `session-*` folders to find the next available number
2. Create the next session folder (auto-increment: `session-1`, `session-2`, ...)
3. Create `00-explanation.md` with the session overview
4. Start fixing — each fix attempt gets its own numbered file

---

## Session Folder Structure

```
fixing-codebase/
├── AGENTS.md                          # This workflow definition
├── session-1/
│   ├── 00-explanation.md              # Session overview (created first)
│   ├── 01-fix-<short-name>.md         # Fix attempt #1
│   ├── 02-fix-<short-name>.md         # Fix attempt #2 (retry if needed)
│   └── 03-fix-<other-bug>.md          # Fix attempt #3 (different bug)
├── session-1-human-check/             # Human-verified testing checklist
│   └── 00-test-scenarios.md           # Steps + expected behavior + checkboxes
├── session-2/
│   ├── 00-explanation.md
│   ├── 01-fix-xxx.md
│   └── ...
├── session-2-human-check/
│   └── 00-test-scenarios.md
└── session-N/
    ├── 00-explanation.md
    └── ...
```

Each `NN-fix-*.md` file covers one fix attempt. If a fix fails and needs a retry, a new numbered file is created. Multiple bugs in one session each get their own numbered file.

---

## Human Testing Checklist

After each session's fixes are applied, a `session-N-human-check/00-test-scenarios.md`
file is created with scenarios for a human to verify manually.

### Purpose
- Confirm fixes actually work in the running application
- Catch regressions or side effects
- Document expected behavior for each fix
- Provide a way to report failures concretely

### How It Works
1. Agent creates `session-N-human-check/00-test-scenarios.md` after all fixes are done
2. Human opens the app and goes through each scenario step by step
3. Each scenario has: steps, expected behavior, and a checkbox
4. Human marks `[x]` if it worked, `[ ]` if it didn't
5. If something fails, human pastes scenario details to the agent
6. Agent investigates and creates a retry fix

### File Template
```markdown
# Session N — Human Testing Checklist

**URL:** http://localhost:7008
**Docker logs:** `docker compose logs -f backend`

## How to Use
1. Open the app in your browser
2. Open DevTools Console (F12 → Console tab)
3. Run `docker compose logs -f backend` in a terminal
4. Go through each scenario below in order
5. Mark `[x]` if it worked, `[ ]` if it didn't

## S1: Scenario name (Fixes X, Y)
**Steps:** ...
**Expected:** ...
- [x] Worked
- [ ] Didn't work — what happened:

## Final Summary
| Scenario | Status |
|----------|--------|
| S1: name | Done |
| ... | Done |
```

---

## Templates

### `00-explanation.md` — Session Overview

```markdown
# Session N — Bug Fixes Overview

**Date:** YYYY-MM-DD HH:MM
**Status:** IN PROGRESS | COMPLETED
**Project:** agentic-project
**Agent:** opencode

## Summary
Brief description of what this session addresses.

## Fixes in this Session

| # | Fix File | Bug | Status |
|---|----------|-----|--------|
| 1 | 01-fix-xxx.md | Description | PENDING |
| 2 | 02-fix-xxx.md | Description | PENDING |

## Verification
- [ ] All fixes applied
- [ ] Backend container rebuilt
- [ ] Frontend container rebuilt (if needed)
- [ ] No syntax errors
- [ ] Smoke test passed
```

### `NN-fix-<short-name>.md` — Individual Fix

```markdown
# Fix N: <Short Title>

**Status:** PENDING | DONE | FAILED | NEEDS RETRY

## Bug Description
What is broken and why it matters.

## Root Cause
Technical explanation of why this happens.

## Files Changed
| File | What changed |
|------|-------------|
| `path/to/file.py` | Lines X-Y: description |

## What Was Done
Step-by-step description of the fix applied.

## Verification
- [ ] File syntax check passed
- [ ] Backend container rebuilt successfully
- [ ] Frontend container rebuilt (if applicable)
- [ ] No runtime errors in logs
- [ ] Manual smoke test passed
- [ ] Specific test case: <description>

## Notes
Any additional context, trade-offs, or follow-up items.
```

---

## Agent Rules

1. **Auto-create session folders** — when told to fix, check existing `session-*` folders and create the next one
2. **Always start with `00-explanation.md`** — before writing any fix files, create the session overview
3. **One file per fix attempt** — if a fix fails and needs retry, create a new numbered file (don't overwrite)
4. **Update docs immediately after each step** — don't batch; update after fix, after rebuild, after verification
5. **Rebuild containers after changes** — run `docker compose build <service> && docker compose up -d <service>` and record the command
6. **Verify before marking DONE** — at least one verification step must pass before status changes to DONE
7. **Reference the project AGENTS.md** — follow rebuild rules, port mappings, and conventions from `agentic-project/AGENTS.md`
8. **Never skip documentation** — even if the fix seems obvious, write the file

---

## Status Values

| Status | Meaning |
|--------|---------|
| `PENDING` | Not started yet |
| `IN PROGRESS` | Fix being worked on |
| `DONE` | Fix applied and verified successfully |
| `FAILED` | Fix applied but verification failed |
| `NEEDS RETRY` | Fix failed — a new attempt is needed |

---

## Verification Checklist (for each fix)

Before marking a fix as `DONE`, complete at least these checks:

- [ ] Syntax / type check passes
- [ ] Backend container rebuilt and starts
- [ ] Frontend container rebuilt (if frontend files were changed)
- [ ] `docker compose ps` shows all services healthy
- [ ] No new errors in backend logs
- [ ] Manual smoke test of the affected feature

---

## Rebuild Commands Reference

| Change type | Command |
|-------------|---------|
| Backend `.py` files | `docker compose build backend && docker compose up -d backend` |
| Frontend `.tsx`/`.ts`/`.css` files | `docker compose build frontend && docker compose up -d frontend` |
| Dockerfile / requirements.txt / package.json | `docker compose build --no-cache <service> && docker compose up -d <service>` |
| `docker-compose.yml` | `docker compose down && docker compose build && docker compose up -d` |
| Env vars only | `docker compose restart <service>` |
| Full DB reset | `docker compose down -v && docker compose up -d` |

Run these from the `agentic-project/` directory.
