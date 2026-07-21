# Manager Agent: Production Hardening Plan (Bugfixes + Architecture)

**Supersedes/extends:** `01-aims-plans-time-flow.md` (2026-07-14) — see [§1 Reconciliation](#1-reconciliation-with-the-2026-07-14-plan) for what from that plan is done vs. still open.
**Date:** 2026-07-15
**Scope:** `components/new-01-manager-agent` only. `components/01-manager-agent` is a superseded, unused predecessor — do not touch it as part of this plan; it is not deployed (confirm via `docker inspect manager_agent_backend --format '{{.Config.Image}}'` → `new-01-manager-agent-backend`).

**How to use this document:** Read §1–§3 fully before changing anything — several bugs here look independent but share a root cause (the LLM-as-router pattern in `analyst.py`). §4 is the actionable roadmap; §5 is file-by-file reference; §6 is how to verify each fix without guessing.

---

## Table of Contents

1. [Reconciliation with the 2026-07-14 plan](#1-reconciliation-with-the-2026-07-14-plan)
2. [Root cause pattern behind almost every bug found](#2-root-cause-pattern-behind-almost-every-bug-found)
3. [Bugs found and fixed on 2026-07-15](#3-bugs-found-and-fixed-on-2026-07-15)
4. [Roadmap to production grade](#4-roadmap-to-production-grade)
5. [Files touched / reference map](#5-files-touched--reference-map)
6. [How to verify (since there is no working automated test suite)](#6-how-to-verify)
7. [Known-open items (not yet fixed, needs a decision)](#7-known-open-items)

---

## 1. Reconciliation with the 2026-07-14 plan

The prior plan (`01-aims-plans-time-flow.md`) diagnosed 17 issues (2.1–2.4, 3.1–3.13). Before doing anything else, a fresh agent should know **most of it is already implemented** — re-implementing would duplicate work or reintroduce bugs this plan just fixed.

| Old plan item | Status as of 2026-07-15 | Evidence |
|---|---|---|
| 2.1 Structured/color-coded suggested aims | ✅ Done | `tools/fetch_schema.py` returns `{aim, dataset, role, kpi_value}`; `ChatSection.tsx` groups by dataset with role labels |
| 2.2 Single focused proposal on suggested-aim selection | ⚠️ Was implemented but **buggy** — fixed 2026-07-15 | See [§3.1](#31-selected_suggested_aim-flag-was-silently-dropped-by-langgraph) and [§3.2](#32-exact-string-match-never-fired-for-typed-follow-ups) |
| 2.3 Feasibility assessment for custom aims | ✅ Done | `feasible` / `feasibility_reason` / `alternative` fields present and populated in live testing |
| 2.4 Time default notification | ✅ Done | `time_default_notice` present in `session_store.py` `build_ui_summary()` |
| 3.1 "confirm N" vs "__confirm__" mismatch | ⚠️ Was implemented but **wrong semantics** — fixed 2026-07-15 | The old plan's own proposed fix made `confirm N` fall straight through to execution. That's actually wrong product behavior — see [§3.5](#35-confirm-n-executed-immediately-instead-of-showing-a-review-step) |
| 3.2 "more options" routing to generate_plans | ✅ Done | Guard exists in `analyst.py` (`"more options" in user_message.lower()...`) |
| 3.3 Duplicate `_build_planner_schema_payload` | ✅ Done | Extracted to `agents/manager/utils/schema_utils.py` |
| 3.4 Cancel/undo after confirm | ❌ Not done | No cancel action found in `confirm_plan.py` or `ChatSection.tsx` (only an unrelated "Cancel" button for the free-text "change something" input) — see [§7](#7-known-open-items) |
| 3.5 `tool_call_count` hard stop → graceful degradation | ✅ Done, message improved further | `analyst.py` already routes to `generate_plans`/`answer_advisory` at the limit; 2026-07-15 additionally replaced the generic "I've gathered enough information" filler with an honest, actionable message — see [§3.7](#37-generic-fallback-message-was-misleading) |
| 3.6 Feedback loop for failed custom aims (clickable alternative) | ✅ Done | `OptionCard` renders a "Try instead: {alternative}" button |
| 3.7 Reset `explore_phase` on new line mention | ✅ Done | `analyst.py`: `if session_json.get("line",{}).get("mention") and not ...resolved: state["explore_phase"] = None` |
| 3.8 TypeScript type for `suggested_aims` | ✅ Done | `frontend/src/types/manager.ts` has the structured type |
| 3.9 `data_available_from` exposed to frontend | ✅ Done | Present in schema payload during live testing |
| 3.10 Join hints in UI | ✅ Done | "Cross-table analysis available" text present in `ChatSection.tsx` |
| 3.11 Advisory word limit | ✅ Done | `advisory_answer.md`: "Keep the answer under 400 words..." |
| 3.12 Granular loading state | ✅ Done | `statusMessage` + rotating `statusSteps` in `sessionStore.ts` |
| 3.13 `seen_proposal_titles` in `PERSISTED_STATE_KEYS` | ✅ Done | Present in `session_store.py` |

**Net new work from the old plan: only 3.4 (cancel/undo) remains genuinely unimplemented.** Everything else below is new — found by actually exercising the running app on 2026-07-15, not by static review.

---

## 2. Root cause pattern behind almost every bug found

Read this before touching code — it explains why five "unrelated-looking" bugs had the same shape.

`analyst.py` implements a **ReAct-style agent loop**: at every turn, an LLM call (`get_llm_client()`, model `qwen36-35B` via local vLLM, see `docker-compose.yml`) reads a JSON dump of the session state (`_build_session_json`) and an 11-rule English prompt (`prompts/analyst.md`), then decides in freeform natural language which Python tool to call next. This is fundamentally different from a deterministic state machine — the "control flow" is a model's judgment call, repeated every step, including for decisions that don't need judgment (e.g. "the user clicked a specific option — call confirm_plan").

Three concrete failure modes recur throughout this codebase because of this:

1. **Prompt under-specification → inconsistent routing.** If a rule isn't spelled out with an example, the model sometimes gets it right and sometimes doesn't, for the exact same input pattern, on different turns. This caused: extraction failing to recognize "vinayaka" as a line name from "tell me about vinayaka" ([§3.6](#36-line-extraction-failed-for-conversational-phrasing)), and the model sometimes not routing `confirm N` to `confirm_plan` ([§3.8](#38-confirm-n-routing-was-never-explicitly-documented-for-the-llm)).
2. **State schema drift.** `ManagerState` (a `TypedDict` in `state.py`) is the source of truth for what LangGraph tracks as "state" between nodes. If a node sets a key that isn't declared in that TypedDict, LangGraph does not propagate it to the next node's input — it's silently dropped. This is not documented anywhere and bit us in [§3.1](#31-selected_suggested_aim-flag-was-silently-dropped-by-langgraph). There is also a **second**, independent list — `PERSISTED_STATE_KEYS` in `session_store.py` — that governs what survives *across HTTP turns* (via DB persistence + `runner.py`'s `_default_state()` reconstruction). These two lists can drift independently; nothing enforces they stay in sync. `plan_proposals` in `state.py` is a currently-dead field (declared, never read or written anywhere) — likely a leftover from a rename to `analysis_proposals`; worth deleting during cleanup.
3. **Frontend infers backend outcomes indirectly instead of being told directly.** The frontend guessed "was this plan actually confirmed?" by checking whether the *next* chat message matched a regex, instead of the backend just saying so. This is a design smell: any state the UI needs to react to should be an explicit field in the API response, not inferred from message text patterns. See [§3.4](#34-frontend-inferred-execution-from-message-text-instead-of-actual-status).

**Implication for future work:** every time you're about to fix "the model didn't do X," ask first whether X can be made deterministic in Python instead of hoping a better prompt fixes it permanently. See [§4 Phase 3](#phase-3--shrink-the-llms-job-description-highest-leverage-structural-change) for the structural fix.

---

## 3. Bugs found and fixed on 2026-07-15

Each entry: symptom → root cause → fix → files. All were verified against the live running app (not just theorized) — see [§6](#6-how-to-verify) for how.

### 3.1 `selected_suggested_aim` flag was silently dropped by LangGraph

**Symptom:** Asking a follow-up question matching a registry-suggested aim (e.g. "average cost by fruit" after seeing it in a suggestions list) produced a plan with 4 unrelated aims concatenated together, instead of just the one asked about.

**Root cause:** `analyst.py` sets `state["selected_suggested_aim"] = ...` to flag "the user picked a known suggested aim, narrow the proposal to just this one" for `tools/generate_plans.py` to consume. But `selected_suggested_aim` was never declared as a field in the `ManagerState` TypedDict (`state.py`). LangGraph only propagates keys that are part of the declared schema between node executions — an undeclared key set on the state dict is silently dropped on the next node call. So `generate_plans.py` always saw `None` and fell back to unioning every in-play proposal's aims into the plan.

**Fix:** Added `selected_suggested_aim: str | None` to `ManagerState` in `state.py`.

**Caveat found during verification:** even after this fix, the flag *still* didn't reliably survive **across separate HTTP turns** (as opposed to within one turn's graph execution) — see [§3.3](#33-cross-turn-state-did-not-reliably-survive-moved-off-the-flag-entirely). That's why the final design ([§3.3](#33-cross-turn-state-did-not-reliably-survive-moved-off-the-flag-entirely)) stopped depending on this flag for the actual narrowing logic and only uses it for a same-call gate in `analyst.py` (`has_aim` check, line ~339). The field stays in the schema; just don't design new cross-turn logic around it.

---

### 3.2 Exact string match never fired for typed follow-ups

**Symptom:** Same as §3.1, compounding it — even once the flag was fixed to propagate, it still never got set for realistic user input.

**Root cause:** `analyst.py`'s match check was `aim == user_message` (exact string equality) against the full registry sentence, e.g. `"Calculate average cost by fruit for the FRUITS_TEST line using the fruits dataset."` A user typing `"average cost by fruit"` will never equal that full sentence.

**Fix:** Changed to case-insensitive substring matching in both directions (`user_norm in aim_norm or aim_norm in user_norm`) in `analyst.py`.

---

### 3.3 Cross-turn state did not reliably survive — moved off the flag entirely

**Symptom:** "More options" (asking for fresh alternative proposals) kept incorrectly reusing the previously-selected aim from the *prior* turn, producing a thin generic explanation ("This analysis focuses on...") instead of fresh proposals.

**Root cause:** Investigated extensively (see conversation transcript for the full trace) — `state["selected_suggested_aim"] = None` (explicit clear, not `.pop()`) worked correctly for the *very next* node call within the same turn's graph execution, but did **not** reliably survive into the *next* HTTP turn's first `analyst()` call. This session's checkpoint-resume behavior (LangGraph `MemorySaver`, keyed by `thread_id = session_id`, combined with `runner.py`'s `_default_state()` reconstructing a fresh partial state dict from DB-loaded `existing_state` on every HTTP call) resurrected a stale mid-turn value rather than the true end-of-turn value. The exact mechanism was not fully pinned down (would require instrumenting LangGraph's checkpointer internals) — but the fix sidesteps the question entirely rather than depending on getting it right.

**Fix:** Stopped relying on any state flag surviving between calls for this decision. `tools/generate_plans.py` now has `_match_registry_suggested_aim(user_message, suggested_aims)` — a pure function that recomputes the match **fresh, every call**, directly from `state["user_message"]` and `state["line_context"]["suggested_aims"]`, both of which *are* reliably reconstructed every turn (verified: `user_message` is set fresh in `runner.py` from the HTTP request body every time; `line_context` is explicitly in `_default_state()`'s carried-forward field list). No flag, no cross-turn dependency, no ambiguity about checkpoint semantics.

**General lesson for this codebase:** don't design new logic that depends on a custom state key surviving unmodified across an HTTP turn boundary unless you've explicitly added it to *both* `ManagerState` (`state.py`) and `PERSISTED_STATE_KEYS` (`session_store.py`) **and** verified it survives with a real multi-turn test — the propagation guarantees here are less solid than they look.

---

### 3.4 Frontend inferred execution from message text instead of actual status

**Symptom:** After the backend was fixed to show a review card when picking one of several proposals (instead of auto-executing — see §3.5), the frontend still displayed "Confirmed — sent to execution" instead of the review card.

**Root cause:** `ChatSection.tsx`: `const confirmedByNextTurn = !!nextTurn && isControlMessage((nextTurn.user || "").trim());` — `isControlMessage()` returns true for **both** `"__confirm__"` (actual execution) and `/^confirm\s+\d+$/` (mere selection). Once the backend started treating `confirm N` as "select for review" rather than "execute," this frontend heuristic became wrong — it can't distinguish the two anymore by message shape alone.

**Fix:** Narrowed the check to the literal execution signal only: `(nextTurn.user || "").trim() === "__confirm__"`.

**Structural note:** this class of bug (frontend re-deriving backend intent from a message string) is fragile by construction. Better long-term fix: have the backend include an explicit `executed: boolean` (or similar) field in the turn response, and have the frontend key off that instead of pattern-matching the next turn's raw text. Flagged as a cleanup item in [§7](#7-known-open-items).

---

### 3.5 "confirm N" executed immediately instead of showing a review step

**Symptom (reported directly by the product owner, not from static analysis):** clicking one of several proposal options went straight to "Confirmed — sent to execution," with no chance to review the single narrowed plan or back out via "More options" / "Change something."

**Root cause:** `analyst.py`'s `confirm_plan` handler treated `"confirm N"` (pick option N from a list) identically to `"__confirm__"` (the literal "Go — proceed" button) — both fell through to actually calling the `tool_confirm_plan` node, which publishes to the planner and marks the task executed. This matches what the *old* 2026-07-14 plan itself proposed (§3.1 there) — that proposed fix was reasonable given the bug it was solving (the pattern wasn't recognized at all), but it never separated "select an option" from "confirm execution" as distinct user intents. That distinction is a deliberate product requirement, not a pre-existing bug fix.

**Fix:** In `analyst.py`, the `confirm N` branch now:
1. Narrows `plan` to the selected proposal's aims/benefits (as before).
2. **Also narrows `analysis_proposals` down to `[selected]`** — this is what flips `build_ui_summary()`'s action-button logic (in `session_store.py`) from `"See more options"` (shown while `len(proposals) > 1`) to `"Go — proceed"` / `"More options"` (shown for a single `plan`).
3. Builds a review message ("Here's the analysis plan for **X**: Title\n\n**Aims:**...") and returns with `phase = "ask"`, `tool_to_call = None` — i.e. **does not** proceed to `tool_confirm_plan`.
4. Only a subsequent, separate `"__confirm__"` message (the actual "Go — proceed" click) reaches `tool_confirm_plan` and executes.

Verified end-to-end: pick option → review card with correct single-aim plan and Go-proceed/More-options buttons, `done: false` → click Go-proceed → `phase: "man"`, "Analysis plan saved and sent to the execution pipeline."

---

### 3.6 Line extraction failed for conversational phrasing

**Symptom:** "tell me about vinayaka" (and originally "fruits test") looped through `extract_slots` roughly a dozen times, each time with the analyst's own reasoning correctly noting "the message contains a potential line mention 'vinayaka'" — yet the extraction never actually populated `slots.line.mention`, until the `tool_call_count >= 10` circuit breaker fired and produced a generic, unhelpful "I've gathered enough information" message.

**Root cause:** Traced with temporary debug logging directly into the running container (see conversation transcript) — the `extract_slots` LLM call (separate from the `analyst` call, using `prompts/extract_slots.md`) consistently returned `"line_mention": null` for this phrasing. `extract_slots.md` had no examples and no guidance distinguishing "the user named an entity" from "the user is asking something informational" — the model was being conservative and returning null for anything not phrased like an explicit command.

**Fix:** Rewrote `extract_slots.md`'s rules to explicitly state that conversational framing ("tell me about X", "what do you know about X", "show me X") still counts as naming X as `line_mention`, that a wrong guess is harmless (a separate `resolve_line` tool validates against the registry afterward and reports "not found" cleanly), and that `null` should be reserved for messages with no candidate name at all. Added five concrete examples covering both the failure case and the "genuinely nothing to extract" case.

**Verified against:** "tell me about vinayaka" (fixed), "fruits test" (the original first-ever failure from earlier in this session, now fixed), "what can you tell me about AM307A" (correctly extracts + correctly reports "not found," since AM307A isn't a real line in this dataset), "hi, what can you help me with" (correctly extracts nothing, gives a helpful generic response instead of looping).

---

### 3.7 Generic fallback message was misleading

**Symptom:** When the `tool_call_count >= 10` circuit breaker fires without ever resolving a schema, the user sees "I've gathered enough information. Let me summarize what I know and suggest next steps." — which is false; nothing was actually gathered, and no summary follows.

**Fix:** In `analyst.py`, this branch now:
- If a line mention was captured but never resolved, names it: *"I couldn't resolve **{mention}** to a known production line. Could you double-check the spelling, or give me the exact line name?"*
- If nothing was captured at all: *"I couldn't figure out which production line or machine you're asking about. Could you tell me the exact line name (e.g. FRUITS_TEST)?"*
- Also clears the stuck `slots.line.mention` so the next message gets a clean retry instead of looping into the same dead end (since §3.6 mostly prevents this class of failure now, but this is a legitimate defensive backstop for any future prompt regression or genuinely unresolvable input).

---

### 3.8 "confirm N" routing was never explicitly documented for the LLM

**Symptom:** Reported directly ("options disappear and it goes back to a list") — inconsistent, not reproducible on every attempt. Selecting an option sometimes correctly narrowed to a review card (see §3.5), and sometimes instead silently produced a *fresh* batch of 3 different proposals, which visually looks like "it reverted" even though it's actually new content.

**Root cause:** `prompts/analyst.md`'s decision rules explicitly named only the literal `"__confirm__"` token for routing to `confirm_plan` (rule 9, in the original numbering). `"confirm N"` was never mentioned as a trigger for that rule anywhere in the prompt — the model had to *generalize* that `"confirm 2"` should be treated the same way, and this generalization wasn't reliable. When it failed, the ambiguous wording of the "generate_plans" rule ("all slots ready, plan proposals missing") let the model interpret `plan` being `None` (which is true right up until confirm_plan actually runs) as "proposals are missing," even though `analysis_proposals` already had entries — triggering a fresh `generate_plans` call instead.

**Fix:** Rewrote `prompts/analyst.md`'s decision rules:
- New rule 1 (highest priority, checked before anything else): *"user message is exactly `__confirm__` OR matches `confirm N` → ALWAYS call confirm_plan, regardless of any other state... never re-generate or re-propose in this case."*
- Clarified the generate_plans rule to explicitly say *"Do NOT call this if `analysis_proposals` already has entries."*

Verified with a repeated trial run (pick "more options" → confirm an option, multiple times) — see conversation transcript; testing was interrupted by the user before completing 3/3 planned trials, **so this needs 2+ more clean repeated-trial verifications before being considered fully confirmed** (this class of bug is inherently probabilistic — see [§2](#2-root-cause-pattern-behind-almost-every-bug-found)). Flagged in [§6](#6-how-to-verify).

---

### 3.9 No auto-scroll to new turns

**Symptom:** After the backend correctly produced a narrowed review card (§3.5), the UI appeared unchanged from the user's perspective — the new turn was appended below the visible scroll position with no indication to scroll down. This directly caused the user to click the same option a second time (on the still-visible, stale 3-option list), which then failed with "Invalid proposal selection" since the proposal list had already been narrowed to 1 item server-side — compounding confusion.

**Fix:** Added a `useEffect` in `ChatSection.tsx` keyed on `turns.length` that calls `scrollContainerRef.current.scrollTo({ top: scrollHeight, behavior: "smooth" })` whenever a new turn is appended. A `ref` was added to the scrollable turns container.

---

### 3.10 Dev environment: no hot-reload, every fix required a full rebuild

**Not a product bug, but blocked fast iteration on everything above.**

**Fix:** `docker-compose.yml` changes:
- `backend` service: added `volumes: [./backend:/app]`, changed `command` to add `--reload` to the `uvicorn` invocation. (Required `chmod +x docker-entrypoint.sh` on the host — the bind mount replaces the image's copy of this file with the host's, and the host copy had lost its executable bit.)
- `frontend` service: added `volumes: [./frontend:/app, /app/node_modules]` (the second entry is an anonymous volume protecting the container's installed `node_modules` from being shadowed by the host's, which may not have them installed at all).

**Caveat:** this compose file is now dev-only. Before any production deployment, a separate compose file (or override) without these bind mounts is required — see [§7](#7-known-open-items).

---

## 4. Roadmap to production grade

### Phase 1 — Deterministic guardrails (do this first; days, not weeks)

Every bug in §3 that was "intermittent" (3.6, 3.8) is the LLM being trusted with a decision that code can make reliably instead. This phase converts the highest-value ones:

1. **Move `confirm N` / `__confirm__` routing out of the LLM's hands entirely.** Currently `analyst.py` still asks the LLM to decide `action`/`tool` first, and *then* has a deterministic regex check inside the `tool == "confirm_plan"` branch — but reaching that branch at all requires the LLM to have already chosen `confirm_plan` as the tool, which is exactly what §3.8 showed is not 100% reliable even with a clearer prompt. **Add a pre-check at the very top of `analyst()`** (before any LLM call): if `user_message` matches `^confirm\s+\d+$` or equals `__confirm__`, skip the LLM call for this turn entirely and go straight to the existing deterministic logic. This removes the failure mode categorically instead of reducing its probability.
2. **Real circuit breaker, not just a call counter.** Track which tool was called on each of the last N steps; if the same tool repeats 3× with no meaningful state change (e.g. `line.mention` unchanged, `phase` unchanged), abort immediately with the improved honest message (§3.7) rather than waiting for `tool_call_count >= 10`. Today's loops burned 60–90+ seconds of real wall-clock time even though they were doomed from the first repeat.
3. **Add a wall-clock timeout per turn** (e.g. 30–45s) independent of tool-call count — a few loops observed during today's testing took a long time in real seconds even while technically making "progress" toward the count limit.

### Phase 2 — Observability

1. **Fix `smoke_test.py`.** It currently fails to even import: `ModuleNotFoundError: No module named 'agents.manager.nodes'` — a leftover reference to the old `01-manager-agent` architecture (which had a `nodes/` package; this rewrite doesn't). This is the only existing test harness for this component and it is completely dead. Either rewrite it against the current `analyst.py` / `tools/*.py` architecture, or replace it with a focused pytest suite. At minimum, cover:
   - The exact scenarios in §3.1–§3.5 (aim narrowing, confirm-vs-select) as unit tests calling `tool_generate_plans` / `analyst` directly with constructed state dicts and a mocked LLM — this is fast, deterministic, and doesn't need the LLM's cooperation (see the throwaway verification script used during today's session for the pattern: build a minimal state dict, patch `get_llm_client` to return a fixed `FakeResponse`, call the function directly, assert on the result).
   - §3.6/§3.8's prompt-dependent behavior is harder to unit test deterministically (it depends on the actual model's behavior) — cover these with a documented manual QA checklist instead (see [§6](#6-how-to-verify)), or a nightly integration run against the real vLLM endpoint if that's affordable.
2. **Structured per-turn tracing.** `harness/tracer.py` and the `/manager/sessions/{id}/trace` endpoint already exist — audit whether they capture the analyst's tool decisions and reasoning per step, or just some subset. Today's debugging required grepping raw container stdout by timestamp, which doesn't scale and won't be available to whoever runs this in an environment without shell access to the container.

### Phase 3 — Shrink the LLM's job description (highest-leverage structural change)

Currently a single model call decides "what tool to call next" from an 11-rule prompt, every single step, for the entire conversation (`analyst.py` + `analyst.md`). Only a few of those steps are genuinely generative (need language understanding): reorganizing a free-text aim, writing plan proposals with business-value framing, writing final advisory summaries. Everything else — slot extraction *should* still be LLM-driven since it's parsing free text, but line resolution, time resolution, schema fetching, and plan confirmation are **not judgment calls** — they're deterministic given the current state.

Recommendation: collapse the ReAct loop into an explicit state machine (much closer to what `01-manager-agent`, the predecessor, actually was — whatever its own bugs, it didn't have this category of "model picked the wrong tool" failure) where code drives the sequence deterministically, and the LLM is invoked only for the 2–3 steps that truly need it. This is a bigger, riskier change than anything else in this document — do it only after Phase 1 and Phase 2 are solid, and treat it as its own project with its own plan document, not a quick patch.

### Phase 4 — Model and prompt quality

1. `qwen36-35B` via local vLLM (`docker-compose.yml`: `MANAGER_MODEL=qwen36-35B`, `VLLM_BASE_URL=http://host.docker.internal:8009/v1`) is the instruction-following bottleneck behind §3.6 and §3.8. Before investing further in prompt tuning, benchmark this exact decision loop against a stronger model (even temporarily, e.g. swap `VLLM_BASE_URL`/`MANAGER_MODEL` in `.env`) to establish how much of the remaining flakiness is "prompt ambiguity" (fixable) vs. "model capability ceiling" (only fixable by Phase 3 or a bigger model). This tells you whether Phase 3 is optional polish or a hard requirement.
2. Add few-shot examples to every prompt that makes a discrete decision. Done so far: `extract_slots.md` (§3.6), `analyst.md` (§3.8). Still needs the same treatment: `propose_analysis_plans.md`, `reorganize_aim.md`.

### Phase 5 — Production hygiene

1. **Separate dev vs. prod Docker Compose.** The bind mounts added in §3.10 (`./backend:/app`, `./frontend:/app`) are a dev convenience — do not ship a production container with host source bind-mounted in. Add a `docker-compose.prod.yml` (or an override file) that builds a self-contained image without these mounts, and document which one to use where.
2. **Resolve the `01-manager-agent` vs. `new-01-manager-agent` ambiguity.** The old directory is dead code sitting in the repo with no indication it's unused — it confused this session's investigation before the actual running component was identified via `docker inspect`. Either delete it, or add a clear `README.md` at the repo root of `components/01-manager-agent/` stating it is superseded and not deployed.
3. **Audit `ManagerState` (`state.py`) vs. `PERSISTED_STATE_KEYS` (`session_store.py`) for drift**, per [§2](#2-root-cause-pattern-behind-almost-every-bug-found). Remove the dead `plan_proposals` field from `state.py`. Consider adding a test that fails CI if a new field is added to one list without a corresponding, deliberate decision recorded for the other (even just a code comment enumerating "intentionally not persisted" fields, e.g. `tool_call_count`, `analyst_reasoning`, `tool_to_call`, `tool_result`, `error`, `agent_message`, `selected_suggested_aim`).

---

## 5. Files touched / reference map

| File | What changed on 2026-07-15 |
|---|---|
| `backend/agents/manager/state.py` | Added `selected_suggested_aim: str | None` field |
| `backend/agents/manager/analyst.py` | Fuzzy suggested-aim matching (§3.2); `confirm N` now reviews instead of executes (§3.5); improved fallback message + line-mention reset (§3.7) |
| `backend/agents/manager/tools/generate_plans.py` | Fresh per-call `_match_registry_suggested_aim()` instead of cross-turn flag dependency (§3.3); fuzzy matching for the "already-narrowed-to-1-by-the-model" case, keeping its real benefits text instead of a generic placeholder |
| `backend/agents/manager/prompts/extract_slots.md` | Added explicit guidance + examples for conversational line-mention phrasing (§3.6) |
| `backend/agents/manager/prompts/analyst.md` | Rule 1 now explicitly covers `confirm N`; generate_plans rule clarified to not fire when `analysis_proposals` already has entries (§3.8) |
| `frontend/src/sections/ChatSection.tsx` | `confirmedByNextTurn` narrowed to literal `__confirm__` only (§3.4); auto-scroll-to-bottom effect on new turns (§3.9) |
| `docker-compose.yml` | Dev-only bind mounts + `--reload` for both services (§3.10) |
| `backend/docker-entrypoint.sh` | `chmod +x` restored on host (required for the bind mount to work) |

---

## 6. How to verify

There is no working automated test suite for this component (see Phase 2). Until that's fixed, verify via the live API — this is exactly how every fix above was actually confirmed, not guessed:

```bash
# Create a session and drive it through curl, e.g.:
curl -s -X POST http://localhost:4002/manager/sessions -d '{}' -H "Content-Type: application/json"
# → {"session_id": "..."}
curl -s -X POST http://localhost:4002/manager/sessions/<id>/messages \
  -H "Content-Type: application/json" -d '{"message":"FRUITS_TEST"}'
# then feed the next message, reading ui.plan.aims / ui.proposals / ui.actions from the JSON response
```

**Regression checklist to re-run after any future change to `analyst.py` / `generate_plans.py` / their prompts:**

1. Ask a suggested aim verbatim from the registry list → exactly 1 aim in the resulting plan, with a real (non-generic) benefits explanation.
2. Ask a paraphrased version of a suggested aim (e.g. "average cost by fruit" when the registry says the same thing) → same as above, not 3+ unrelated aims.
3. "More options" after a plan is shown → 3 *genuinely different* proposals, no reappearance of earlier unrelated topics.
4. Pick one of several proposals (`confirm N` equivalent, i.e. click an OptionCard) → review card for just that one plan, `done: false`, actions = `[Go — proceed, More options]`. **Run this 3+ times in fresh sessions** — §3.8's fix was only verified once before being interrupted; this is the one item in this document that most needs re-confirmation.
5. Click "Go — proceed" after step 4 → `phase: "man"`, plan actually sent to execution.
6. Ask about a line using conversational phrasing ("tell me about X", not just the bare canonical name) → resolves without looping.
7. Ask about a line name that doesn't exist → clean "not found" message, not a loop.
8. A message with no line name at all ("hi, what can you help with") → helpful generic response, not a loop.

---

## 7. Known-open items

Not fixed as part of this session — listed so the next person doesn't have to rediscover them:

1. **§3.4 from the 2026-07-14 plan (cancel/undo after confirm) is still open.** No way to cancel a plan between "Go — proceed" and the planner actually picking it up.
2. **§3.8 here needs 2 more clean verification trials** (see §6 item 4) — it was fixed and passed once, but the user interrupted before completing the planned 3-trial check, and this exact class of bug is probabilistic by nature (§2).
3. **Frontend "confirmedByNextTurn" heuristic (§3.4) is patched, not structurally fixed.** The backend should expose an explicit `executed: boolean` field in the turn response instead of the frontend inferring it from message text shape.
4. **No production Docker Compose file.** The dev bind mounts added in §3.10 must not ship as-is.
5. **`01-manager-agent` (old component) is unlabeled dead code** in the repo — should be deleted or clearly marked superseded.
6. **`plan_proposals` field in `state.py` is dead** (declared, never used) — safe to delete, but do a repo-wide grep first to be certain before removing.
7. **Phase 3 (shrinking the LLM's job description) is a significant architectural change**, not attempted here — this document only hardens the current ReAct-loop design; it does not replace it.
