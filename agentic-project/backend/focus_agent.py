"""Tool-calling agent loop for single-aim FOCUS mode.

Replaces the old single-shot "generate SQL in a markdown block, then interpret in a
second call" pipeline with a real multi-round tool-calling conversation: the model
chooses between querying fresh data and recalling a result already fetched earlier
in this session, self-correcting when a recalled result doesn't actually cover the
question.
"""

import json
import re
import unicodedata
import logging
from difflib import get_close_matches

from config import get_settings, get_llm_client
from sql_executor import validate_sql, execute_sql
from sqlite_executor import execute_sql as execute_sqlite_sql
from llm_client import language_instruction
from logger import log_sql

logger = logging.getLogger(__name__)


def normalize_halfwidth(text: str) -> str:
    """Convert half-width katakana to full-width so the LLM can read them properly.
    Half-width katakana (e.g. ﾜｰｸ) are valid Unicode but uncommon in modern text and
    cause the LLM to hallucinate □ replacement characters."""
    return unicodedata.normalize("NFKC", text)


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "query_data",
            "description": (
                "Run a NEW SQL query against the attached datasets. Use this for any topic "
                "not already listed as available via recall_result, or when you need a "
                "different breakdown than what a previous result contains."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "A single SELECT/WITH SQL query. Use the exact SQL table names given in the dataset context.",
                    }
                },
                "required": ["sql"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recall_result",
            "description": (
                "Fetch rows from a previously executed query in this session, as listed in "
                "the 'Previously fetched' context below. No new SQL is run. If the returned "
                "columns don't answer the question, call query_data instead."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "reference": {
                        "type": "string",
                        "description": "The aim/topic name exactly as listed in the 'Previously Fetched' context.",
                    }
                },
                "required": ["reference"],
            },
        },
    },
]

AGENT_SYSTEM_PROMPT = """You are a data analysis assistant. Current mode: RESEARCH — FOCUSED ANALYSIS (agentic).

You have two tools available:
- query_data(sql): run a brand-new SQL query.
- recall_result(reference): reuse rows already fetched earlier in this session, instead of querying again.

## Available Datasets And Aims
{context}

## Previously Fetched In This Session
{previously_fetched}
{language_instruction}

## How To Decide
- If the question can be answered from something already listed above under "Previously Fetched", call recall_result with that reference first — don't re-query data you already have.
- If recall_result's returned columns don't actually cover what's being asked, call query_data next with a query that gets the right breakdown. Do not guess or make up numbers.
- If the topic isn't listed under "Previously Fetched" at all, call query_data directly.
- Before writing SQL, verify every column name exists in its table by checking the schema above.
- Only use columns and tables from the datasets listed above. Use the exact SQL table name given in parentheses for each dataset.
- Always include LIMIT 100 in any SQL you run unless the user asks for all results.

## CRITICAL — Never Give Up On SQL Errors
- If query_data returns ANY error (column not found, syntax error, type mismatch), you MUST fix the mistake and retry with corrected SQL. A SQL error is ALWAYS a retry signal, NEVER an answer signal.
- You MUST NOT respond with "I cannot execute", "I cannot run the query", or any variation of giving up. "I cannot execute" is NEVER an acceptable final answer.
- If you don't know the correct column name, look at the schema above and pick the closest match from the listed columns.
- Only answer without data if you have exhausted the last available tool round (the system will tell you when no more tool calls are available).
- If query_data returns 0 rows, broaden the query (fewer joins, looser filters) and retry once before concluding no data exists.
- Once a tool call returns a valid, usable result (rows > 0), answer from it. Do not call query_data again for the same question just to double-check or rephrase the same query.

## Your Final Answer
Once you have enough information, respond with plain text (no more tool calls):
- If this is a factual question ("what/which/how many..."), give the direct answer, 1-2 notable observations, and one follow-up question.
- If this is an advisory question (e.g. "what can be done to improve/increase/fix..."), you MUST give 2-3 concrete, actionable recommendations grounded in the data you gathered — not just a restatement of the numbers, and not only a deflecting question.
- End your final answer with one line: [CHART_DECISION: yes] or [CHART_DECISION: no] — yes if the data you used has 3+ rows and multiple columns worth comparing, no otherwise.
"""


def _extract_chart_decision(text: str) -> tuple[bool, str]:
    # Defensive: some chat templates leak a literal <tool_call> attempt into content
    # when no tools are offered (e.g. the forced final round) — strip it rather than
    # show broken XML-like text to the user.
    text = re.sub(r'<tool_call>.*?(</tool_call>|$)', '', text, flags=re.DOTALL | re.IGNORECASE).strip()
    match = re.search(r'\[CHART_DECISION:\s*(yes|no)\]', text, re.IGNORECASE)
    chart_needed = bool(match and match.group(1).lower() == "yes")
    clean = re.sub(r'\s*\[CHART_DECISION:\s*(yes|no)\]\s*', ' ', text, flags=re.IGNORECASE).strip()
    return chart_needed, clean


def _topic_label(turn: dict) -> str:
    """Short topic label derived from what was actually asked, not the formal aim name —
    matches how users naturally reference past results ('that banana data') rather than
    the pinned aim's formal title ('Category Performance Analysis')."""
    user_text = (turn.get("user") or "").strip()
    return user_text[:80] if user_text else "previous result"


def _build_previously_fetched_section(session_state: dict, attached_aims: list[str]) -> str:
    """List (topic, columns, row_count) for the most recent stored result per attached aim."""
    turns = session_state.get("turns", [])
    chat_results = session_state.get("chat_query_results", {})
    lines = []
    for aim in attached_aims:
        match = None
        for t in reversed(turns):
            if aim in (t.get("aims") or []):
                match = t
                break
        if not match:
            continue
        result_uuid = match.get("result_uuid")
        r = chat_results.get(result_uuid) if result_uuid else None
        if not r:
            continue
        cols = ", ".join(r.get("columns", []))
        topic = _topic_label(match)
        lines.append(f'- "{topic}" ({r.get("row_count", 0)} rows: {cols})')
    return "\n".join(lines) if lines else "(nothing fetched yet this session for the attached aim(s))"


def _build_column_map(datasets_data: list[dict]) -> dict[str, set[str]]:
    """Build a map of table_name -> set of known column names from column_definitions.
    column_definitions may be a list of {name, ...} dicts or a direct dict of name->description."""
    col_map: dict[str, set[str]] = {}
    for d in datasets_data:
        table = d.get("table", "")
        cdefs = d.get("column_definitions") or {}
        if isinstance(cdefs, dict):
            col_map[table] = set(cdefs.keys())
        elif isinstance(cdefs, list):
            col_map[table] = {c.get("name", "") for c in cdefs if isinstance(c, dict)}
    return col_map


def _suggest_column_fix(error_msg: str, column_map: dict[str, set[str]]) -> str:
    """If the error mentions a missing column, find the closest match and append did-you-mean."""
    m = re.search(r"no such column:\s*(\S+)", error_msg, re.IGNORECASE)
    if not m:
        m = re.search(r"column\s+\"?(\w+)\"?\s+does not exist", error_msg, re.IGNORECASE)
    if not m:
        return error_msg
    bad_col = m.group(1)
    # Strip table alias prefix if any (e.g. "a.異常№" -> "異常№")
    bad_col_short = bad_col.split(".")[-1] if "." in bad_col else bad_col
    all_known: set[str] = set()
    for cols in column_map.values():
        all_known.update(cols)
    if bad_col_short in all_known:
        return error_msg
    suggestions = get_close_matches(bad_col_short, list(all_known), n=3, cutoff=0.3)
    if suggestions:
        return f"{error_msg} Did you mean: {', '.join(suggestions)}?"
    return error_msg


async def _run_query_data(sql: str, datasets_data: list[dict] | None = None) -> dict:
    try:
        validated = validate_sql(sql)
    except ValueError as e:
        return {"ok": False, "error": f"SQL validation failed: {e}"}

    # Personal (uploaded CSV) datasets live in the user's own SQLite file, separate
    # from the shared Postgres global_registry datasets — route to whichever engine
    # actually holds the table(s) this query references.
    datasets_data = datasets_data or []
    sqlite_tables = {d["table"]: d.get("sqlite_path") for d in datasets_data if d.get("backend") == "sqlite"}
    pg_tables = {d["table"] for d in datasets_data if d.get("backend", "pg") == "pg"}
    referenced_sqlite = [t for t in sqlite_tables if re.search(rf'\b{re.escape(t)}\b', validated, re.IGNORECASE)]
    referenced_pg = [t for t in pg_tables if re.search(rf'\b{re.escape(t)}\b', validated, re.IGNORECASE)]

    if referenced_sqlite and referenced_pg:
        return {
            "ok": False,
            "error": (
                "This query mixes a personal uploaded dataset with a shared dataset — "
                "they live in separate databases and cannot be joined directly. Query them separately."
            ),
        }

    column_map = _build_column_map(datasets_data)

    try:
        if referenced_sqlite:
            result = await execute_sqlite_sql(sqlite_tables[referenced_sqlite[0]], validated)
        else:
            result = await execute_sql(validated)
        log_sql("agent_tool_call", f"query_data: {validated[:150]}")
        # Normalize half-width katakana in result so the LLM doesn't hallucinate □ characters
        if result and result.get("rows"):
            normalized_rows = []
            for row in result["rows"]:
                normalized_rows.append({
                    k: normalize_halfwidth(v) if isinstance(v, str) else v
                    for k, v in row.items()
                })
            result["rows"] = normalized_rows
        return {"ok": True, "result": result}
    except Exception as e:
        msg = str(e)[:300]
        msg = _suggest_column_fix(msg, column_map)
        return {"ok": False, "error": f"SQL execution failed: {msg}"}


_STOPWORDS = {"the", "a", "an", "of", "for", "and", "to", "that", "this", "data", "show", "me", "get"}


def _run_recall_result(reference: str, session_state: dict) -> dict:
    turns = session_state.get("turns", [])
    chat_results = session_state.get("chat_query_results", {})
    reference_lower = reference.lower().strip()
    reference_words = {w for w in re.findall(r"[a-z0-9]+", reference_lower) if w not in _STOPWORDS and len(w) > 2}
    match = None
    for t in reversed(turns):
        # Match against the topic (what was actually asked) as well as the formal
        # aim/dataset tags — "banana data" should hit a turn tagged only by aim name
        # if its own question text mentions bananas.
        topic_words = set(re.findall(r"[a-z0-9]+", _topic_label(t).lower()))
        tags = [a.lower() for a in (t.get("aims") or [])] + [d.lower() for d in (t.get("datasets") or [])]
        tag_hit = any(reference_lower in tag or tag in reference_lower for tag in tags)
        topic_hit = bool(reference_words & topic_words)
        if tag_hit or topic_hit:
            match = t
            break
    if not match:
        return {"found": False, "message": f"No previously fetched result matches '{reference}'."}
    result_uuid = match.get("result_uuid")
    r = chat_results.get(result_uuid) if result_uuid else None
    if not r:
        return {"found": False, "message": f"No stored rows for '{reference}'."}
    return {
        "found": True,
        "columns": r.get("columns", []),
        "column_types": r.get("column_types", []),
        "rows": r.get("rows", []),
        "row_count": r.get("row_count", 0),
        "sql": r.get("sql", ""),
    }


async def run_focus_agent(
    message: str,
    context: str,
    attached_aims: list[str],
    enrichment_block: str,
    session_state: dict,
    max_rounds: int = 6,
    datasets_data: list[dict] | None = None,
    language: str = "en",
) -> dict:
    """Agentic FOCUS loop: the LLM chooses between querying fresh data and recalling
    a previously fetched result in this session, across up to max_rounds tool-call turns.
    Returns {agent_message, chart_needed, query_result} — query_result is the raw dict
    from execute_sql (no chart_suggestions attached yet), or None if no query ran."""
    settings = get_settings()
    client = get_llm_client()

    # If this aim+datasets combo already has a successful focus result in this session,
    # hide the "Previously Fetched" section. Otherwise the LLM may pivot to "explain
    # from schema" when a fresh query errors, instead of retrying.
    is_rerun = False
    turns = session_state.get("turns", [])
    for t in reversed(turns):
        if t.get("route") == "focus" and t.get("aims") == attached_aims:
            is_rerun = True
            break

    if is_rerun:
        previously_fetched = ""
    else:
        previously_fetched = _build_previously_fetched_section(session_state, attached_aims)
    system_prompt = AGENT_SYSTEM_PROMPT.format(
        context=context,
        previously_fetched=previously_fetched,
        language_instruction=language_instruction(language),
    )
    if enrichment_block:
        system_prompt += f"\n\n## Previous Context\n{enrichment_block}"

    messages: list[dict] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": message},
    ]

    last_query_result: dict | None = None

    for round_num in range(max_rounds):
        is_last_round = round_num == max_rounds - 1
        if is_last_round:
            # Force a final text answer using whatever was gathered so far — without
            # this, a model that second-guesses itself can burn every round re-calling
            # tools on the same question and never actually answer.
            messages.append({
                "role": "user",
                "content": (
                    "No more tool calls are available. You must answer now, in plain natural "
                    "language only, using whatever information was already gathered above. "
                    "Do NOT write <tool_call> tags, function-call syntax, or any XML-like block — "
                    "that will not be executed and will just be shown to the user as broken text. "
                    "If what you have isn't quite enough, say so honestly and answer as best you can "
                    "rather than attempting another action."
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
        response = await client.chat.completions.create(**create_kwargs)
        msg = response.choices[0].message

        if not msg.tool_calls:
            chart_needed, clean = _extract_chart_decision(msg.content or "")
            return {"agent_message": clean, "chart_needed": chart_needed, "query_result": last_query_result}

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
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                tool_result = {"ok": False, "error": "Malformed tool call arguments — please retry with valid JSON."}
            else:
                if tc.function.name == "query_data":
                    tool_result = await _run_query_data(args.get("sql", ""), datasets_data)
                    if tool_result.get("ok"):
                        last_query_result = tool_result["result"]
                elif tc.function.name == "recall_result":
                    tool_result = _run_recall_result(args.get("reference", ""), session_state)
                    log_sql("agent_tool_call", f"recall_result: {args.get('reference', '')}")
                    if tool_result.get("found"):
                        # Give a recall-based answer its own fresh Output panel card too —
                        # the user should be able to check the data behind ANY answer,
                        # not just ones that ran a brand-new query.
                        last_query_result = {
                            "sql": tool_result.get("sql", ""),
                            "columns": tool_result.get("columns", []),
                            "column_types": tool_result.get("column_types", []),
                            "rows": tool_result.get("rows", []),
                            "row_count": tool_result.get("row_count", 0),
                        }
                else:
                    tool_result = {"ok": False, "error": f"Unknown tool '{tc.function.name}'"}

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(tool_result, default=str)[:4000],
            })

    # Round cap exhausted without a final plain-text answer — degrade gracefully,
    # same shape as today's "no SQL found" fallback in _handle_focus.
    last_content = ""
    for m in reversed(messages):
        if m.get("role") == "assistant" and m.get("content"):
            last_content = m["content"]
            break
    chart_needed, clean = _extract_chart_decision(
        last_content or "I wasn't able to complete this within the allotted steps — could you rephrase or narrow the question?"
    )
    return {"agent_message": clean, "chart_needed": chart_needed, "query_result": last_query_result}
