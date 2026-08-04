"""Template-report pipeline — a separate, isolated agent that fills in a user's
free-text format spec from the attached datasets.

This is intentionally NOT a research flow:
- No aims, no proposals, no suggestions, no [Action] blocks, no route classification.
- Pure inputs: attached datasets + the user's format spec.
- The LLM decides what data the report needs, runs as many SQL queries as required
  (e.g. per-metric max/average/min/last value, per-machine sections), reusing data
  already fetched this session when it can, then writes the report EXACTLY in the
  user's format.

It reuses the battle-tested tool helpers from focus_agent (query_data / recall_result)
so behaviour (retry on SQL error, column-fix hints, half-width normalisation) matches
the rest of the app, but it has its own prompt and its own round budget.
"""

import json
import re
import logging

from config import get_settings, get_llm_client
from llm_client import language_instruction
from logger import log_sql
from focus_agent import (
    TOOLS,
    normalize_halfwidth,
    serialize_tool_result,
    _run_query_data,
    _run_recall_result,
)

logger = logging.getLogger(__name__)


def _last_assistant_content(messages: list[dict]) -> str:
    """Scan backwards for the most recent non-empty assistant text."""
    for m in reversed(messages):
        if m.get("role") == "assistant" and m.get("content"):
            return m["content"]
    return ""


def split_format_spec(format_spec: str) -> tuple[list[str], str]:
    """Split a template format spec into its numbered analysis sections plus any
    trailing `Notes:` block (applied to every section). Returns (sections, notes).

    A numbered section starts with a line like `1)` / `2.` at line start. Indented
    lines (e.g. `   Explanation: ...`) belong to the preceding section. The `Notes:`
    block is extracted wherever it appears so it can be appended to each section.
    """
    notes: list[str] = []
    main: list[str] = []
    in_notes = False
    for ln in format_spec.splitlines():
        stripped = ln.strip()
        if re.match(r"^notes\s*:", stripped, re.IGNORECASE):
            in_notes = True
            notes.append(stripped)
            continue
        if in_notes:
            if re.match(r"^\s*\d+[\)\.]", ln):
                in_notes = False
                main.append(ln)
            else:
                notes.append(ln)
            continue
        main.append(ln)

    body = "\n".join(main).strip()
    notes_text = "\n".join(notes).strip()
    if not body:
        return ([format_spec.strip()] if format_spec.strip() else [""], notes_text)

    sections: list[str] = []
    cur: list[str] = []
    for ln in body.splitlines():
        if re.match(r"^\s*\d+[\)\.]", ln) and cur:
            sections.append("\n".join(cur))
            cur = [ln]
        else:
            cur.append(ln)
    if cur:
        sections.append("\n".join(cur))
    return sections, notes_text


def _build_previous_section(session_state: dict) -> str:
    """List the most recent stored results in this session so recall_result can reuse
    data already gathered instead of re-querying."""
    turns = session_state.get("turns", [])
    chat_results = session_state.get("chat_query_results", {})
    lines = []
    for t in reversed(turns):
        if len(lines) >= 5:
            break
        result_uuid = t.get("result_uuid")
        r = chat_results.get(result_uuid) if result_uuid else None
        if not r:
            continue
        user_text = (t.get("user") or "").strip()[:80] or "previous result"
        cols = ", ".join(r.get("columns", []))
        lines.append(f'- "{user_text}" ({r.get("row_count", 0)} rows: {cols})')
    return "\n".join(lines) if lines else "(nothing fetched yet this session)"


TEMPLATE_SYSTEM_PROMPT = """You are a report generator working from the attached datasets.

The user provided a strict report format and a question. Your job: gather the data the report
needs, then fill in the report EXACTLY in that format. This is NOT a research or exploration
task — do not propose aims, suggestions, follow-up ideas, or [Action] blocks. Just query the
data and write the completed report.

## Available Datasets
{context}

## Previously Fetched In This Session
{previously_fetched}

## Report Format (STRICT)
{format_spec}

## How To Decide
- Read the format spec carefully. It may ask for any combination of values, metrics, analysis,
  or per-machine/per-item sections (e.g. max, average, min, last value, trends, comparisons).
  Interpret it for the current situation.
- For every value or fact the report needs, decide:
  - If the data was already fetched in this session and covers it, call recall_result to reuse it.
  - Otherwise, call query_data to run a NEW SQL query for it.
- When you call query_data, pass a short `note` (one phrase, in the report language) describing what the
  query returns — e.g. "machine names found in the production table" — it is shown as that table's caption.
- Run as many queries as the report needs. If several metrics share the same grouping, batch
  them into one query when possible (e.g. SELECT machine, MAX(v), AVG(v), MIN(v) FROM ... GROUP BY machine).
- Always use SQL aggregation (MAX/AVG/MIN/COUNT) for aggregates — NEVER compute numbers in your head.
- Always include LIMIT 100 unless you need all rows.
- If a query returns 0 rows, broaden it (fewer filters) and retry once before concluding no data.
- If a query errors, fix the SQL and retry. A SQL error is a retry signal, never an answer.
- Do NOT call query_data again for the same question just to double-check or rephrase the same query.
  Once a query succeeds, use its result. If you need a different breakdown, run a NEW, more specific query.
- If a tool result says `"rows_truncated": true`, the result was larger than the display cap
  (up to 200 rows are shown in full). Do NOT re-run that same query unchanged to "get the rest" —
  run a more targeted query (e.g. one machine, or a single metric) for the specific rows you still
  need. A truncated display is NEVER a reason to write "No data" or "unavailable" — the data exists,
  query for it more narrowly.

## Round Budget
- You have at most {max_rounds} tool-call rounds for this report. Be economical: batch several
  metrics into a single query when possible (e.g. SELECT machine, MAX(v), AVG(v), MIN(v) ... GROUP BY machine),
  and you may issue multiple query_data calls in a single round.
- Once you have the data a section needs, write that section's report immediately. Do NOT spend extra
  rounds re-checking, re-running, or exploring "just in case" — the report is judged on content, not on
  how many queries you ran. If a needed value is missing after the data you gathered, write "No data".

## CRITICAL RULES
- Every number in the report MUST come from an actual query result. Never invent or guess values.
- Cover EVERY attached dataset: run each numbered analysis for every attached dataset unless the format
  explicitly asks for combined data. Never silently drop a dataset or reuse one dataset's numbers for another.
- When a section asks for per-machine values, get ALL machines at once with ONE query that groups by the
  machine column (e.g. SELECT 機番, 時間帯, COUNT(*) ... GROUP BY 機番, 時間帯). Do NOT run a separate query
  per machine, and never write that a machine's data is "not available" unless a targeted query for it
  returned nothing.
- If the format spec contains a `Notes:` section, treat it as strict constraints from the analyst (e.g. which
  column to group by or use). Follow it exactly.
- Each numbered analysis may be followed by its OWN `Explanation:` line, indented under that number. That
  explanation applies to THAT analysis section ONLY — do not mix or reuse one analysis' explanation for another.
  Interpret the data gathered for that section to answer exactly those points. If a numbered analysis has no
  `Explanation:` line (or it is empty), write a generic interpretation for that section: overall trend, notable
  anomalies (NG spikes, empty hours, torque outliers), and the practical implication — grounded ONLY in the actual
  query results, never invent numbers, and do not run a query for the explanation.
- Only reference columns that are actually listed in the dataset schemas above (each dataset shows its
  exact SQL table name and its columns with their meanings).
- Use the EXACT SQL column name shown for each column (the name before any "(original header: ...)" note) —
  the schema may show a friendlier original header name in parentheses, but the SQL column name is the one
  that exists in the table. If a column name starts with a digit or contains characters other than letters,
  digits, and underscore, you MUST double-quote it in SQL, e.g. "c_5st内径値1".
- Map each '?' field in the format spec to a column ONLY when the column name OR its stated meaning
  actually matches what the field asks for. If a requested metric or column does not exist in ANY
  attached dataset, write "No data" for that field — NEVER pick a different column merely because it
  is numeric, and NEVER repurpose an unrelated column to fill it.
- If data for a field could not be gathered, write "No data" in that field — never fabricate it.
- The report must contain ONLY the sections/structure from the format spec. No extra headings,
  no recommendations, no [Action] blocks, no suggested follow-up questions.
- Name the specific column(s) you used to derive each number in the report.
- FORMAT THE REPORT AS MARKDOWN, not a plain prose dump:
  - Keep the exact numbered structure from the format spec (1), 2), ...), but make each section heading a
    markdown heading or bold line (e.g. "**1) ...**").
  - Write each section's `Explanation:` as a short one-line lead-in followed by a markdown bullet list
    (`- `), one point per line. Do not fold everything into a single paragraph.
  - **Bold** the key numbers/values inside each bullet.
  - Keep the numbered sections/headings identical to the format spec — only the body text becomes bullets.
  - Do NOT echo the format spec's own instruction text (e.g. "1) Explain the trend...") back into the
    report — write your own lead-in sentence based on the actual query results.

## Your Final Answer
Once you have enough information, respond with the completed report text (no more tool calls).
Do not wrap it in code blocks or add commentary around it.
{language_instruction}
"""


async def run_template_agent(
    message: str,
    context: str,
    format_spec: str,
    datasets_data: list[dict] | None = None,
    session_state: dict | None = None,
    language: str = "en",
    max_rounds: int | None = None,
    on_progress: callable = None,
) -> dict:
    """Agentic loop for the template-report pipeline.

    Returns {agent_message, query_result, query_results, truncated, stopped_reason} —
    query_result is the raw dict from the LAST executed query/recall (used for chart
    suggestions), query_results is the list of every successful query/recall in order,
    and truncated is True only when the run hit an LLM error (stopped_reason "error")
    or exhausted the loop without producing a report (stopped_reason "budget").
    Producing the report on the final allowed round is a NORMAL completion, not a
    truncation — the final round simply strips tools and asks for the report.
    stopped_reason is "" on a clean completion.
    """
    settings = get_settings()
    client = get_llm_client()
    session_state = session_state or {}

    previously_fetched = _build_previous_section(session_state)
    system_prompt = TEMPLATE_SYSTEM_PROMPT.format(
        context=context,
        previously_fetched=previously_fetched,
        format_spec=format_spec,
        language_instruction=language_instruction(language),
        max_rounds=max_rounds if max_rounds else settings.template_max_rounds,
    )

    messages: list[dict] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": message},
    ]

    last_query_result: dict | None = None
    all_query_results: list[dict] = []
    max_rounds = max_rounds if max_rounds else settings.template_max_rounds
    executed_sql: set[str] = set()

    def _record_result(res: dict) -> None:
        """Keep every successful query/recall in order so the UI can show all the data
        that fed the report, not just the last query."""
        nonlocal last_query_result
        last_query_result = res
        all_query_results.append(res)

    for round_num in range(max_rounds):
        is_last_round = round_num == max_rounds - 1
        if on_progress:
            on_progress(f"template_round_{round_num}", "running", f"Round {round_num + 1}/{max_rounds}")
        if is_last_round:
            messages.append({
                "role": "user",
                "content": (
                    "No more tool calls are available. Produce the completed report NOW, in plain "
                    "text, following the Report Format above exactly. Fill every section from the "
                    "data you already gathered. Where data is missing, write 'No data'. Do NOT write "
                    "<tool_call> tags, function-call syntax, or any XML-like block."
                ),
            })
        create_kwargs = dict(
            model=settings.llm_model,
            messages=list(messages),
            max_tokens=settings.max_tokens,
            temperature=settings.temperature,
            extra_body={"chat_template_kwargs": {"enable_thinking": False}},
        )
        if not is_last_round:
            create_kwargs["tools"] = TOOLS
            create_kwargs["tool_choice"] = "auto"
        if on_progress:
            on_progress(f"template_round_{round_num}_llm", "running", "Thinking...")
        try:
            response = await client.chat.completions.create(**create_kwargs)
        except Exception as e:
            logger.error("template_agent LLM call failed", extra={"error": str(e)[:300]})
            if on_progress:
                on_progress(f"template_round_{round_num}_llm", "error", "LLM call failed")
                on_progress(f"template_round_{round_num}", "done", "Stopped early")
            last_content = _last_assistant_content(messages)
            return {
                "agent_message": last_content or "I hit an error while gathering data for the report. Please try again.",
                "query_result": last_query_result,
                "query_results": all_query_results,
                "truncated": True,
                "stopped_reason": "error",
            }
        msg = response.choices[0].message
        if on_progress:
            on_progress(f"template_round_{round_num}_llm", "done", "Response received")

        if not msg.tool_calls:
            # A plain-text report is a normal completion whether the model chose to
            # write it early or was guided to write it on the final round — the last
            # round simply strips tools and asks for the report, it is not a failure.
            # The report is never flagged "incomplete" just because it landed on the
            # final round; only a real LLM error or loop exhaustion flags it.
            if on_progress:
                on_progress(f"template_round_{round_num}", "done", "Report ready")
            return {
                "agent_message": msg.content or "",
                "query_result": last_query_result,
                "query_results": all_query_results,
                "truncated": False,
                "stopped_reason": "",
            }

        messages.append({
            "role": "assistant",
            "content": msg.content or "",
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in msg.tool_calls
            ],
        })

        for tc in msg.tool_calls:
            if tc.function.name == "query_data":
                try:
                    args = json.loads(tc.function.arguments or "{}")
                    tool_detail = f"query: {args.get('sql', '')[:80]}"
                except json.JSONDecodeError:
                    args = {}
                    tool_detail = "query_data (malformed args)"
            elif tc.function.name == "recall_result":
                try:
                    args = json.loads(tc.function.arguments or "{}")
                    tool_detail = f"recall: {args.get('reference', '')[:60]}"
                except json.JSONDecodeError:
                    args = {}
                    tool_detail = "recall_result (malformed args)"
            else:
                args = {}
                tool_detail = f"unknown tool: {tc.function.name}"
            if on_progress:
                on_progress(f"template_round_{round_num}_tool", "running", tool_detail)
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                tool_result = {"ok": False, "error": "Malformed tool call arguments — please retry with valid JSON."}
            else:
                if tc.function.name == "query_data":
                    sql = (args.get("sql") or "").strip()
                    norm_sql = " ".join(sql.split())
                    if norm_sql and norm_sql in executed_sql:
                        tool_result = {
                            "ok": False,
                            "error": "This exact query already ran successfully above. Use the data already provided and proceed — do not re-run identical SQL.",
                        }
                    else:
                        tool_result = await _run_query_data(sql, datasets_data)
                        if tool_result.get("ok"):
                            _record_result({**tool_result["result"], "note": (args.get("note") or "").strip()})
                            executed_sql.add(norm_sql)
                elif tc.function.name == "recall_result":
                    tool_result = _run_recall_result(args.get("reference", ""), session_state)
                    log_sql("template_agent_tool_call", f"recall_result: {args.get('reference', '')}")
                    if tool_result.get("found"):
                        _record_result({
                            "sql": tool_result.get("sql", ""),
                            "columns": tool_result.get("columns", []),
                            "column_types": tool_result.get("column_types", []),
                            "rows": tool_result.get("rows", []),
                            "row_count": tool_result.get("row_count", 0),
                        })
                else:
                    tool_result = {"ok": False, "error": f"Unknown tool '{tc.function.name}'"}

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": serialize_tool_result(tool_result, settings.template_tool_max_rows),
            })
            if on_progress:
                status = "done" if tool_result.get("ok") or tool_result.get("found") else "error"
                detail = tool_detail
                if not tool_result.get("ok") and tool_result.get("error"):
                    detail += f" — {tool_result['error'][:60]}"
                on_progress(f"template_round_{round_num}_tool", status, detail)

    # Round budget exhausted without a plain-text report — degrade gracefully.
    if on_progress:
        on_progress(f"template_round_{max_rounds - 1}", "done", "Max rounds reached")
    last_content = _last_assistant_content(messages)
    return {
        "agent_message": last_content or "I couldn't complete the report within the allotted steps.",
        "query_result": last_query_result,
        "query_results": all_query_results,
        "truncated": True,
        "stopped_reason": "budget",
    }
