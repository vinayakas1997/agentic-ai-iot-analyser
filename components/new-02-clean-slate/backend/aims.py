"""LLM service — chat responses and aim generation."""

import json
import logging
from openai import AsyncOpenAI
from config import get_settings
from sql_executor import explain_sql, validate_sql_safety, clean_sql

logger = logging.getLogger(__name__)

CHAT_SYSTEM_PROMPT = """You are a data analysis assistant. Help users understand their data, explore possible analyses, and build strategies — all using the datasets provided below.

## Available Datasets
{context}

## Instructions
Based on the user's question, respond appropriately:

1. **EXPLAIN** — If the user asks about specific aims or analysis ideas (e.g., "explain this", "what does this mean"), describe them in detail: what they compute, which columns are used, what insights they reveal.

2. **STRATEGIZE** — If the user asks to combine aims or create a strategy (e.g., "combine these", "create a plan"), present a step-by-step analysis plan that chains the aims together using the available datasets and join relationships.

3. **EXPLORE** — If the user asks "what can I do?" or "what analysis is possible?", suggest 3–5 different analysis directions. For each: name, goal, columns/datasets needed, and expected insight.

4. **FACTUAL** — If the user asks about specific columns, tables, or relationships, answer directly from the schema metadata.

## Rules
- Only reference columns and datasets listed in the context above
- Never invent column names, values, or tables
- If the user selected specific aims (mentioned in their message), prioritize explaining or working with those
- Use markdown (headings, lists, tables, code blocks) for readability
- If the question is unrelated to the available data, politely redirect to what the datasets can actually answer"""


async def call_llm(prompt: str) -> str:
    """Simple LLM call returning text response."""
    settings = get_settings()
    client = AsyncOpenAI(base_url=settings.vllm_base_url, api_key="EMPTY", timeout=settings.llm_request_timeout)
    try:
        response = await client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": "You are a helpful data analysis assistant. Answer questions clearly and concisely."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=settings.max_tokens,
            temperature=settings.temperature,
        )
        return response.choices[0].message.content or ""
    except Exception as e:
        logger.warning(f"call_llm failed: {e}")
        return ""


def build_dataset_context(datasets: list[dict]) -> str:
    """Build markdown context block from dataset registry data."""
    blocks = []
    for ds in datasets:
        name = ds.get("dataset_name") or ds.get("name", "unknown")
        desc = ds.get("description") or ""
        cols = ds.get("column_definitions") or ds.get("columns", [])

        col_rows = "\n".join(
            f"| {c.get('name', '')} | {c.get('datatype', '')} | {c.get('meaning', '')} |"
            for c in cols
        )
        col_section = f"| Column | Type | Meaning |\n|--------|------|---------|\n{col_rows}" if col_rows else "No column definitions."

        hints = ds.get("join_hints") or []
        join_lines = []
        if isinstance(hints, list):
            for h in hints:
                to = h.get("to_dataset", "")
                on = h.get("on", [])
                join_lines.append(f"- joins to **{to}** on `{on}`")
        elif isinstance(hints, dict):
            to = hints.get("to_dataset", "")
            on = hints.get("on", [])
            join_lines.append(f"- joins to **{to}** on `{on}`")
        join_section = "\n".join(join_lines) if join_lines else "None"

        aims = ds.get("suggested_aims") or []
        aim_rows = []
        for a in aims:
            if isinstance(a, dict):
                aim_rows.append(f"- **{a.get('aim', '')}** — {a.get('description', '')}")
            elif isinstance(a, str):
                aim_rows.append(f"- {a}")
        aim_section = "\n".join(aim_rows) if aim_rows else "None"

        blocks.append(
            f"### {name}\n*{desc}*\n\n{col_section}\n\n"
            f"**Joins:**\n{join_section}\n\n"
            f"**Suggested aims:**\n{aim_section}"
        )

    return "\n\n".join(blocks)


SQL_GENERATION_PROMPT = """You are a PostgreSQL query generator. Given the dataset schemas below, write a SQL query that answers the user's question.

## Available Tables
{table_context}

## Rules
- Output ONLY the SQL query — no explanation, no markdown formatting
- Use the exact table names shown in the `###` headers — do NOT add schema qualifiers (write `test_fruits` not `fruits.test_fruits` or `public.test_fruits`)
- The `###` header IS the table name — the bullet points after it are just descriptions, not tables
- Only reference columns listed in the schema
- Use PostgreSQL syntax
- Always include a LIMIT clause (max 200 rows)
- Only SELECT statements are allowed
- Use table aliases when joining multiple tables
- Group and order results appropriately for the question
- Never use CROSS JOIN. Use only INNER JOIN or LEFT JOIN with explicit ON conditions.
- Never use window functions (OVER, PARTITION BY) unless the user explicitly asks for running totals or rankings"""




def build_sql_context(datasets: list[dict]) -> str:
    """Build markdown context block with actual table names for SQL generation."""
    blocks = []
    for ds in datasets:
        name = ds.get("dataset_name", "unknown")
        table = ds.get("table") or name
        desc = ds.get("description") or ""
        cols = ds.get("column_definitions") or ds.get("columns", [])
        col_rows = "\n".join(
            f"- `{c.get('name', '')}` ({c.get('datatype', 'text')}) — {c.get('meaning', '')}"
            for c in cols
        )
        blocks.append(
            f"### {table}\n*{name}: {desc}*\n\nColumns:\n{col_rows}"
        )
    return "\n\n".join(blocks)


async def criticize_sql(
    sql: str,
    message: str,
    datasets_data: list[dict],
) -> dict:
    """Critique a SQL query. Returns {pass: bool, issues: list[str], suggestions: str}.

    Uses fast rule-based checks only: EXPLAIN syntax validation + safety regex.
    No LLM call — keeps latency low and avoids model failures.
    """
    cleaned = clean_sql(sql) or sql

    # 1. Syntax check via EXPLAIN
    try:
        await explain_sql(cleaned)
    except Exception as e:
        return {"pass": False, "issues": [str(e)[:300]], "suggestions": "Fix the syntax error"}

    # 2. Safety checks (forbidden keywords, CROSS JOIN, missing LIMIT, etc.)
    safety = validate_sql_safety(cleaned)
    if safety:
        return {"pass": False, "issues": safety, "suggestions": "Fix safety violations"}

    return {"pass": True, "issues": [], "suggestions": ""}


SQL_FIX_PROMPT = """You are a PostgreSQL query fixer. The SQL query below failed with the following error:

{error}

## Original User Request
{message}

## Original SQL (FAILED)
```sql
{bad_sql}
```

## Fix Suggestions
{suggestions}

## Rules
- Fix the SQL to resolve the error
- Output ONLY the fixed SQL query — no explanation, no markdown formatting
- Use the exact table names shown in the `###` headers
- Use PostgreSQL syntax
- Always include a LIMIT clause (max 200 rows)
- Only SELECT statements are allowed
- Use table aliases when joining multiple tables
- Use unique column aliases in CTEs to avoid ambiguous column references"""


async def fix_sql(
    bad_sql: str,
    error: str,
    message: str,
    datasets_data: list[dict],
    suggestions: str = "",
) -> str:
    """Ask the LLM to fix a broken SQL query."""
    context = build_sql_context(datasets_data)
    system_prompt = SQL_GENERATION_PROMPT.replace("{table_context}", context)

    fix_prompt = SQL_FIX_PROMPT.format(
        error=error[:500],
        message=message,
        bad_sql=bad_sql,
        suggestions=suggestions,
    )

    settings = get_settings()
    client = AsyncOpenAI(base_url=settings.vllm_base_url, api_key="EMPTY", timeout=settings.llm_request_timeout)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": fix_prompt},
    ]

    response = await client.chat.completions.create(
        model=settings.llm_model,
        messages=messages,
        max_tokens=settings.max_tokens,
        temperature=settings.temperature,
    )
    return response.choices[0].message.content or ""


async def generate_sql(
    message: str,
    datasets_data: list[dict],
    history: list[dict] | None = None,
) -> str:
    """Generate a SQL query from a user message and dataset context."""
    if not datasets_data:
        raise ValueError("At least one dataset is required")

    context = build_sql_context(datasets_data)
    system_prompt = SQL_GENERATION_PROMPT.replace("{table_context}", context)

    settings = get_settings()
    client = AsyncOpenAI(base_url=settings.vllm_base_url, api_key="EMPTY", timeout=settings.llm_request_timeout)

    messages = [{"role": "system", "content": system_prompt}]
    if history:
        messages.extend(history[-10:])
    messages.append({"role": "user", "content": message})

    response = await client.chat.completions.create(
        model=settings.llm_model,
        messages=messages,
        max_tokens=settings.max_tokens,
        temperature=settings.temperature,
    )
    return response.choices[0].message.content or ""


async def generate_chat_response(
    message: str,
    dataset_names: list[str],
    datasets_data: list[dict],
    history: list[dict] | None = None,
) -> str:
    """Generate an LLM chat response using dataset context and conversation history."""
    if not dataset_names or not datasets_data:
        return "Please select at least one dataset to work with. Search and attach datasets from the search bar above."

    context = build_dataset_context(datasets_data)
    system_prompt = CHAT_SYSTEM_PROMPT.replace("{context}", context)

    settings = get_settings()
    client = AsyncOpenAI(base_url=settings.vllm_base_url, api_key="EMPTY", timeout=settings.llm_request_timeout)

    try:
        # Truncate history entries to prevent context overflow
        truncated_history = []
        if history:
            for h in history[-10:]:
                entry = dict(h)
                if isinstance(entry.get("content"), str) and len(entry["content"]) > 1000:
                    entry["content"] = entry["content"][-1000:]
                truncated_history.append(entry)

        messages = [{"role": "system", "content": system_prompt}]
        if truncated_history:
            messages.extend(truncated_history)
        messages.append({"role": "user", "content": message})

        response = await client.chat.completions.create(
            model=settings.llm_model,
            messages=messages,
            max_tokens=settings.max_tokens,
            temperature=settings.temperature,
        )
        return response.choices[0].message.content or ""
    except Exception as e:
        logger.exception("generate_chat_response: LLM failed")
        return f"I encountered an error while processing your request. Please try again. ({str(e)[:200]})"

EXTRACT_AIMS_PROMPT = """Extract specific analysis aims from the research text below. Return ONLY a JSON array — no markdown, no code fences.

Each object in the array must have:
- "aim": short name (2-6 words)
- "description": what this analysis computes or reveals (1 sentence)
- "datasets": list of dataset names to use

If no clear aims, return [].

Text:
{text}"""


async def extract_aims_from_text(text: str, dataset_names: list[str]) -> list[dict]:
    """Extract structured aim proposals from a chat response text."""
    if not text.strip():
        return []

    prompt = EXTRACT_AIMS_PROMPT.format(text=text[:2000])
    try:
        raw = (await call_llm(prompt)).strip()
        if not raw:
            return []
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1]
            raw = raw.rsplit("```", 1)[0]
        aims = json.loads(raw)
        if not isinstance(aims, list):
            return []
        for a in aims:
            if isinstance(a, str):
                a = {"aim": a, "description": "", "datasets": dataset_names}
            if "datasets" not in a or not a["datasets"]:
                a["datasets"] = dataset_names
            if "description" not in a:
                a["description"] = ""
        return aims
    except (json.JSONDecodeError, Exception) as e:
        logger.warning(f"extract_aims_from_text: failed — {e}")
        return []
