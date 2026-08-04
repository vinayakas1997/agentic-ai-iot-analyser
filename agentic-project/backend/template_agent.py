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
- Run as many queries as the report needs. If several metrics share the same grouping, batch
  them into one query when possible (e.g. SELECT machine, MAX(v), AVG(v), MIN(v) FROM ... GROUP BY machine).
- Always use SQL aggregation (MAX/AVG/MIN/COUNT) for aggregates — NEVER compute numbers in your head.
- Always include LIMIT 100 unless you need all rows.
- If a query returns 0 rows, broaden it (fewer filters) and retry once before concluding no data.
- If a query errors, fix the SQL and retry. A SQL error is a retry signal, never an answer.

## CRITICAL RULES
- Every number in the report MUST come from an actual query result. Never invent or guess values.
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
    on_progress: callable = None,
) -> dict:
    """Agentic loop for the template-report pipeline.

    Returns {agent_message, query_result, query_results, truncated, stopped_reason} —
    query_result is the raw dict from the LAST executed query/recall (used for chart
    suggestions), query_results is the list of every successful query/recall in order,
    and truncated is True when the run exhausted its round budget (stopped_reason
    "budget") or hit an LLM error (stopped_reason "error") and had to finish from the
    data gathered so far. stopped_reason is "" on a clean completion.
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
    )

    messages: list[dict] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": message},
    ]

    last_query_result: dict | None = None
    all_query_results: list[dict] = []
    max_rounds = settings.template_max_rounds

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
            truncated = is_last_round
            if on_progress:
                on_progress(
                    f"template_round_{round_num}",
                    "done",
                    "Report ready" if not truncated else "Tool-step limit reached — report may be incomplete",
                )
            return {
                "agent_message": msg.content or "",
                "query_result": last_query_result,
                "query_results": all_query_results,
                "truncated": truncated,
                "stopped_reason": "budget" if truncated else "",
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
                    tool_result = await _run_query_data(args.get("sql", ""), datasets_data)
                    if tool_result.get("ok"):
                        _record_result(tool_result["result"])
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
                "content": json.dumps(tool_result, default=str)[:4000],
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
