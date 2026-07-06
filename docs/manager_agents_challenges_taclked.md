# Manager Agent — Challenges Tackled

Overview of problems the manager agent solves, grouped into three areas for easier reading.

---

## Part 1 — Understanding the user

How the agent interprets who, what, and when before building a plan.

### Three-lane conversation routing

The agent splits user intent into **direct plan**, **explore options**, and **advisory Q&A** so one path does not overwrite another. For example, asking *"what benefit would I get?"* should explain—not rebuild a plan or re-list registry aims.

### Line / machine name resolution

Users rarely type exact catalog names (e.g. *"Vinayaka"* maps to `FRUITS_TEST`). The agent resolves via exact name, synonym, task alias, or asks when ambiguous; it reports not-found when nothing matches.

### Multi-machine sessions

Users may mention several lines in one session (*"Vinayaka and AM307A"*). The agent tracks each as a slot, supports skip/forget, picks an active line, and handles joint vs single-machine scope.

### Slot persistence across turns

Follow-up messages must not lose earlier work. Resolved lines are **lookup-locked** so the agent does not re-resolve or drop machines unless the user explicitly changes them.

### Time phrase handling

Time is optional for many tasks. Relative phrases (*"last week"*, *"past 2 days"*) are parsed against a reference timestamp; ambiguous phrases trigger clarification instead of silent wrong dates.

### LLM extraction fallback

When the extract model returns empty or weak clarification JSON, regex fallbacks handle common patterns (skip machine, wants suggested aims, deeper explore, saved plan commands). This keeps the CLI usable when the LLM misclassifies.

### Chat history for multi-turn context

Recent conversation turns are passed into extract and advisory calls so corrections, typos, and follow-ups (*"tell me more about that"*) are interpreted in context.

---

## Part 2 — Choosing an analysis

How the user discovers, narrows, and shapes what to analyze.

### Tier-1 vs Tier-2 analysis discovery

*"What aims can we do?"* shows a fast registry list (Tier-1). *"Other / deeper options"* triggers LLM-generated proposal batches (Tier-2). The two modes stay separate so "deeper" does not replay the same static list.

### Advisory Q&A without breaking the pipeline

Users ask benefits, follow-ups, schema readiness, and plan explanations mid-session. These route to **`answer_advisory`** so explore/propose logic and aim extraction are not triggered by mistake.

### Strategic follow-up questions (business plan / next steps)

Questions like *"what should be the next business plan?"* were misrouted to the suggested-aims template. Fixed with prompt examples plus a regex safety net so strategy questions get a real advisory answer when a line is already resolved.

### Dataset scope on a line

A line can load multiple tables (e.g. `fruits`, `fruit_quality`). Users can include, exclude, or ask about specific tables without starting a new line session.

### Cross-table join proposals

Explore mode can propose analyses that join datasets (e.g. on `batch_id`) when the join catalog supports it. Proposals stay within loaded schema—no invented tables or columns.

### Explore plan batch — propose, refine, confirm

Tier-2 explore returns 3 numbered proposals. Users can refine (*"keep 1 & 2, change 3"*), select, reject, or confirm into a single runnable plan.

### Saved plan shortlist (S1–S5)

Users can save favorite proposals to a session shortlist and later combine or activate them. This supports iterative planning without losing earlier options.

### Stale plan cleanup on reject

If the user rejects a plan (*"nope, show other options"*), old plan and proposal state is cleared so the next turn does not show outdated aims or proposals.

### IoT column wishes (future data)

Users may ask for columns that do not exist yet (e.g. temperature sensors). These are tracked as **wishes only**—never added to schema or aims as if they were real columns.

---

## Part 3 — Finishing the session

How the user confirms, reuses work, and hands off to downstream agents.

### Session meta questions

Users ask about session state (*"what tables are loaded?"*, *"what's still missing?"*, *"which line is active?"*). These get fast template answers from session inventory—not LLM slot extraction.

### Task reuse from history

Users can reference a prior run (*"same as last Vinayaka analysis"*). The agent pre-fills aims/time from task history when a matching alias is found.

### Confirm shortcut (`go`)

Once a plan exists, a simple *"go"* / *"confirm"* skips re-extraction and saves the task definition for handoff. This avoids re-parsing every confirmation word as a new analysis request.

### Planner / research handoff

On confirmation, the agent builds a structured **`planner_payload`** (task definition, schema slice, dataset scope, IoT wishes) for downstream agents. The manager stops at planning—it does not run analysis itself.

### Comprehensive smoke test coverage

50+ automated tests cover line lookup, multi-line, explore, advisory, meta, dataset scope, task reuse, and full end-to-end flows. This guards against regressions when prompts or routing change.

---

## Related docs

| Doc | Purpose |
|-----|---------|
| [`manager_planner_flow_spec.md`](manager_planner_flow_spec.md) | Three lanes, state buckets, entry conditions |
| [`manger_agent_only_langrph_flow.md`](manger_agent_only_langrph_flow.md) | Full LangGraph node-by-node reference |
| [`maanager_agents_detailed_Architecture.md`](maanager_agents_detailed_Architecture.md) | Architecture overview (TBD) |
