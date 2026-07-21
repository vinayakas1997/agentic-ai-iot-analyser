# Manager → Planner flow spec

Three lanes after line resolution:

| Lane | Trigger | Result |
|------|---------|--------|
| A — Direct plan | machines + aim | `reorganize_aim` → plan + benefits → `go` |
| B — Explore | `more options` | scope menu → optional intention → 3-plan batch → save (max 5) → combine |
| C — Advisory | questions | `answer_advisory` / meta — no propose overwrite |

## State buckets

| Field | Role |
|-------|------|
| `slots` | line, time, aim, line_slots, scope, dataset_context (unchanged) |
| `analysis_proposals` | Temporary explore batch (3 plans) |
| `saved_plans` | Session shortlist S1–S5 |
| `plan` | Active plan for `go` |
| `scope_selection` | `"all"` or canonical line name |
| `scope_pending` | Awaiting numbered scope reply |
| `user_explore_intent` | Optional focus for propose |
| `session_goal` | User-stated session focus |
| `iot_column_wishes` | Suggestions only — never in aims/schema |
| `planner_payload` | Handoff on `go` |

## Entry conditions

1. **Machines only** → sync → ask aim (+ IoT suggested aims ≤3 if present)
2. **Machines + aim** → sync → reorganize → plan (+ benefits)
3. **More options** → scope (if multi-line) → propose batch

## Scope menu (CLI)

1 = All machines (joint); 2..N = single machine.

## Planner handoff

`go` → `send_to_planner` → `planner_payload` with task_definition, schema slice, `iot_column_wishes`.
