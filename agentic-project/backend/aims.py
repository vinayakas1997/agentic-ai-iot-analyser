"""LLM service — chat responses and aim generation."""

import json
import logging
from config import get_settings, get_llm_client
from sql_executor import validate_sql, validate_sql_safety, clean_sql
from query_router import route_explain
from llm_client import build_enrichment_system_prompt, language_instruction
from column_profile import profile_columns

logger = logging.getLogger(__name__)

CHAT_SYSTEM_PROMPT = """You are a data analysis assistant. Help users understand their data, explore possible analyses, and build strategies — all using the datasets provided below.

You are AUTHORIZED to discuss, describe, analyze, and reference data from the provided datasets. It is your job to help the user understand this data.

## Available Datasets
{context}

## Instructions
Based on the user's question, respond appropriately:

1. **EXPLAIN** — If the user asks about specific aims or analysis ideas (e.g., "explain this", "what does this mean"), describe them in detail: what they compute, which columns are used, what insights they reveal.

2. **STRATEGIZE** — If the user asks to combine aims or create a strategy (e.g., "combine these", "create a plan"), present a step-by-step analysis plan that chains the aims together using the available datasets and join relationships.

3. **EXPLORE** — If the user asks "what can I do?" or "what analysis is possible?", suggest 3–5 different analysis directions. For each: name, goal, columns/datasets needed, and expected insight.

4. **FACTUAL** — If the user asks about specific columns, tables, or relationships, answer directly from the schema metadata.

5. **EDUCATE** — If the user asks about data visualization concepts (e.g., "what is an area chart?", "when should I use a bar vs line chart?", "explain scatter plots"), explain the concept clearly with examples. Relate it back to their data where possible.

## Cross-Dataset Analysis
When multiple datasets are attached, identify cross-dataset analysis opportunities:
1. **Find Common Columns** — Look for columns with the same or similar names across datasets (potential join keys)
2. **Identify Relationships** — Use `join_hints` from dataset metadata to understand foreign key relationships
3. **Propose Cross-Dataset Analyses** — Suggest specific analyses that combine datasets

**Suggestion logic:**
- If user asks "what can I do?" or has no clear intention → suggest **3 analysis ideas** (exploratory)
- If user has a specific question or intent → give **ONE comprehensive analysis** tailored to their request
- Keep responses conversational — let the user follow up, ask more, or drill deeper
- Do not overwhelm with multiple unrequested ideas — one step at a time

## Rules
- Only reference columns and datasets listed in the context above
- Never invent column names, values, or tables
- If the user selected specific aims (mentioned in their message), prioritize explaining or working with those
- Use markdown (headings, lists, tables, code blocks) for readability
- If the question is unrelated to the available data AND unrelated to data visualization concepts, politely redirect to what the datasets can actually answer"""


async def call_llm(prompt: str, language: str = "en", temperature: float | None = None) -> str:
    """Simple LLM call returning text response."""
    settings = get_settings()
    client = get_llm_client()
    try:
        response = await client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": "You are a helpful data analysis assistant. Answer questions clearly and concisely." + language_instruction(language)},
                {"role": "user", "content": prompt},
            ],
            max_tokens=settings.max_tokens,
            temperature=temperature if temperature is not None else settings.temperature,
            extra_body={"chat_template_kwargs": {"enable_thinking": False}},
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
- The `[backend: ...]` tag in each `###` header tells you which database that table lives in. NEVER JOIN or reference tables that have different backend tags in the same query — they live in separate databases and cannot be mixed. Query one database per statement.
- Only reference columns listed in the schema
- Use the dialect of the backend tagged in the headers (PostgreSQL for `[postgres:...]`, MySQL for `[mysql:...]`)
- Always include a LIMIT clause (max 200 rows)
- Only SELECT statements are allowed
- Use table aliases when joining multiple tables
- Group and order results appropriately for the question
- If a TEXT column represents a time-of-day or duration in "H:MM" / "HH:MM" format (not zero-padded), NEVER `ORDER BY` it directly — that sorts alphabetically (e.g. "10:20" before "2:20") not chronologically. Instead order by its numeric parts, e.g. `ORDER BY split_part(col, ':', 1)::int, split_part(col, ':', 2)::int`
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
        backend = ds.get("backend", "pg")
        if ds.get("connection_id") and backend != "sqlite":
            tag = f"[{ds.get('db_type') or 'external'}:{name}]"
        elif backend == "sqlite":
            tag = "[personal:sqlite]"
        else:
            tag = "[postgres:main]"
        col_rows = "\n".join(
            f"- `{c.get('name', '')}` ({c.get('datatype', 'text')}) — {c.get('meaning', '')}"
            for c in cols
        )
        blocks.append(
            f"### {table} {tag}\n*{name}: {desc}*\n\nColumns:\n{col_rows}"
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

    # Add LIMIT if missing (validate_sql does this) before safety check
    try:
        validated = validate_sql(cleaned)
    except ValueError as e:
        return {"pass": False, "issues": [str(e)[:300]], "suggestions": "Fix the validation error"}

    # 1. Syntax check via EXPLAIN on the backend owning the referenced table(s)
    try:
        await route_explain(datasets_data, validated)
    except Exception as e:
        return {"pass": False, "issues": [str(e)[:300]], "suggestions": "Fix the syntax error"}

    # 2. Safety checks (forbidden keywords, CROSS JOIN, missing LIMIT, etc.)
    safety = validate_sql_safety(validated)
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
    client = get_llm_client()

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": fix_prompt},
    ]

    response = await client.chat.completions.create(
        model=settings.llm_model,
        messages=messages,
        max_tokens=settings.max_tokens,
        temperature=settings.temperature,
        extra_body={"chat_template_kwargs": {"enable_thinking": False}},
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
    client = get_llm_client()

    messages = [{"role": "system", "content": system_prompt}]
    if history:
        messages.extend(history[-10:])
    messages.append({"role": "user", "content": message})

    response = await client.chat.completions.create(
        model=settings.llm_model,
        messages=messages,
        max_tokens=settings.max_tokens,
        temperature=settings.temperature,
        extra_body={"chat_template_kwargs": {"enable_thinking": False}},
    )
    return response.choices[0].message.content or ""


async def generate_chat_response(
    message: str,
    dataset_names: list[str],
    datasets_data: list[dict],
    history: list[dict] | None = None,
    enrichment_block: str | None = None,
    enrichment_mode: str = "",
    language: str = "en",
) -> str:
    """Generate an LLM chat response using dataset context and conversation history.

    When enrichment_block is provided, it replaces history entirely and is injected
    as system context. The mode-specific system prompt (RESEARCH/SUMMARY) is used
    to instruct the LLM on how to interpret the enrichment block.
    """
    if not dataset_names or not datasets_data:
        if enrichment_mode == "summary":
            context = ""
        else:
            return "Please select at least one dataset to work with. Search and attach datasets from the search bar above."
    else:
        context = build_dataset_context(datasets_data)
    settings = get_settings()
    client = get_llm_client()

    try:
        if enrichment_block:
            system_prompt = build_enrichment_system_prompt(enrichment_mode, context, language=language)
            combined_system = f"{system_prompt}\n\n## Previous Context\n{enrichment_block}"
            messages = [
                {"role": "system", "content": combined_system},
                {"role": "user", "content": message},
            ]
        else:
            system_prompt = CHAT_SYSTEM_PROMPT.replace("{context}", context) + language_instruction(language)
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
            extra_body={"chat_template_kwargs": {"enable_thinking": False}},
        )
        msg = response.choices[0].message
        content = msg.content or ""
        refusal = msg.refusal or ""
        logger.info("generate_chat_response: finish_reason=%s content_len=%d refusal_len=%d role=%s",
                     response.choices[0].finish_reason,
                     len(content), len(refusal),
                     msg.role)
        return content or refusal
    except Exception as e:
        logger.exception("generate_chat_response: LLM failed")
        return f"I encountered an error while processing your request. Please try again. ({str(e)[:200]})"

VALID_CHART_TYPES = {"composed", "stackedArea", "treemap", "radialBar", "funnel", "sunburst", "scatter", "radar",
                     "bar", "line", "area", "pie"}


def _human_label(col: str) -> str:
    return col.replace("_", " ").title()


def _pick_best_x_key(candidates: list[str], rows: list[dict]) -> str:
    """Pick the column with the most distinct values from first 20 rows."""
    if not candidates:
        return ""
    best = candidates[0]
    best_count = -1
    for col in candidates:
        vals = set(str(r.get(col, "")) for r in rows[:20])
        if len(vals) > best_count:
            best = col
            best_count = len(vals)
    return best


BASIC_CHART_TYPES = {"bar", "line", "area", "pie"}
ADVANCED_CHART_TYPES = VALID_CHART_TYPES - BASIC_CHART_TYPES

# Cardinality cap for charts that render one visual element per distinct value
# (treemap tiles, pie/radialBar slices, sunburst arcs) — beyond this the chart
# turns into unreadable confetti rather than a readable comparison.
MAX_SLICE_CARDINALITY = 15


def _check_hierarchy(parent_col: str, child_col: str, rows: list[dict]) -> bool:
    """True only if every child value maps to exactly one parent value
    (a real parent→child hierarchy), not just two unrelated categorical columns."""
    child_to_parent: dict[str, str] = {}
    for r in rows:
        parent = str(r.get(parent_col, ""))
        child = str(r.get(child_col, ""))
        seen_parent = child_to_parent.get(child)
        if seen_parent is None:
            child_to_parent[child] = parent
        elif seen_parent != parent:
            return False
    return bool(child_to_parent)


def _numeric_scale_compatible(numeric_cols: list[str], rows: list[dict]) -> bool:
    """True if the numeric columns are within a comparable order of magnitude —
    radar/composed axes become misleading when one metric dwarfs the others."""
    ranges = []
    for col in numeric_cols:
        nums = []
        for r in rows:
            v = r.get(col)
            try:
                nums.append(float(v))
            except (TypeError, ValueError):
                continue
        if nums:
            ranges.append(max(abs(min(nums)), abs(max(nums)), 1e-9))
    if len(ranges) < 2:
        return True
    return (max(ranges) / min(ranges)) <= 50


def _compute_diagnostics(columns: list[str], column_types: list[str], rows: list[dict]) -> dict[str, dict]:
    """Per-column data-condition facts (distinct count, nulls, zeros, dominant value)
    computed deterministically in Python — the LLM reasons over these, it never
    has to guess them from a text description."""
    profiles = profile_columns(columns, rows)
    n = len(rows) or 1
    for col in columns:
        p = profiles.get(col, {})
        counts: dict[str, int] = {}
        for r in rows:
            v = r.get(col)
            if v is None:
                continue
            counts[str(v)] = counts.get(str(v), 0) + 1
        top_count = max(counts.values()) if counts else 0
        p["dominant_pct"] = round(top_count / n * 100, 1)
    return profiles


def _diagnostics_text(columns: list[str], column_types: list[str], diagnostics: dict[str, dict], row_count: int = 0) -> str:
    type_map = dict(zip(columns, column_types))
    lines = [f"Total rows: {row_count}"] if row_count else []
    for col in columns:
        d = diagnostics.get(col, {})
        samples = ", ".join(repr(s) for s in d.get("common_samples", [])[:3])
        distinct = d.get("distinct_count", 0)
        repeat_note = ""
        if row_count and 0 < distinct < row_count:
            avg_repeat = round(row_count / distinct, 1)
            repeat_note = (
                f", REPEATS: only {distinct} distinct values across {row_count} rows "
                f"(~{avg_repeat}x each) — picking this as xKey means every chart will "
                f"aggregate (sum, or average for radar) the other rows sharing each value; "
                f"only choose it if that grouping matches the analysis"
            )
        lines.append(
            f"- {col} (declared type: {type_map.get(col, 'text')}, detected: {d.get('datatype')}): "
            f"{distinct} distinct values, "
            f"{d.get('null_pct', 0)}% null, "
            f"dominant value covers {d.get('dominant_pct', 0)}% of rows"
            + (f", {d.get('zero_pct')}% zeros" if d.get('zero_pct') else "")
            + (", CONSTANT (only one value)" if d.get('is_constant') else "")
            + repeat_note
            + f" — top values: {samples}"
        )
    return "\n".join(lines)


CHART_SELECTION_PROMPT = """You are a data visualization expert. Choose which chart types genuinely fit this data — not just which ones are structurally possible.

## Chart Type Meanings & When They Are Valid
- **bar**: compare a metric across discrete categories. Always safe.
- **line**: show a trend over an ordered/date axis. Needs an ordered xKey (date or sequential category).
- **area**: like line, emphasizes magnitude/volume over an ordered axis.
- **pie**: show parts of a whole. INVALID if the category has more than {max_slices} distinct values, or if one value dominates >85% of rows (nothing to compare).
- **treemap**: show parts of a whole as nested rectangles, better than pie for many categories but still needs ≤{max_slices} tiles to stay readable.
- **radialBar**: like bar but circular — same cardinality limits as pie.
- **sunburst**: a TRUE two-level hierarchy, where every child category value belongs to exactly one parent category value (e.g. country → city). INVALID if the two categorical columns are actually independent/unrelated — do not use it just because two categorical columns exist. Format: xKey = parent category column, yKeys = [numeric_value_column, child_category_column] (exactly 2 items, numeric column FIRST).
- **scatter**: explore correlation between two numeric columns. Needs 2+ numeric columns that are conceptually related (not e.g. an ID and a price).
- **radar**: compare an entity across 3+ numeric metrics on spokes. INVALID if the metrics are on wildly different scales (e.g. a count in the 10s next to a revenue figure in the millions) since the polygon becomes meaningless.
- **funnel**: show sequential drop-off across ordered stages (e.g. signup → activation → purchase). INVALID unless the categories represent a real progression/process, not an arbitrary grouping.
- **composed**: bars + line overlay for 2+ numeric metrics sharing one xKey.
- **stackedArea**: stacked contribution of 2+ numeric metrics over an ordered xKey.

## Columns & Business Meaning
{column_meanings}

## Computed Data Diagnostics (facts — use these, do not guess)
{diagnostics}

## Sample Rows (first 3)
{sample_rows}

## How to choose xFormat
- **"time"** — xKey contains dates, timestamps, or ordered time periods. This enables smart formatting (e.g., show "14:00" for hourly, "Jan" for monthly, "2024 Q1" for quarterly). Use this when the axis represents a temporal scale.
- **"text"** — xKey contains categorical names, labels, or codes that should be displayed verbatim (e.g. supplier names, product types, status labels).
- **"number"** — xKey contains numeric values on a continuous scale.
- **"auto"** — (default) let the display code decide based on the actual value format.

## Task
Pick every chart type from the list above that is genuinely appropriate for this specific data — reject any whose "INVALID if..." condition is met by the diagnostics above. Always include "bar" unless there are no usable columns. For each chosen chart, give exact column names for xKey/yKeys, a 1-sentence "reason" tied to what the data actually shows, a 1-2 sentence "howToRead" explaining how to interpret it, and xFormat describing how x-axis labels should be displayed.

## Output Format — JSON array only, no markdown, no code fences
[
  {{"chartType": "bar", "xKey": "...", "yKeys": ["..."], "reason": "...", "howToRead": "...", "xFormat": "auto"}},
  ...
]"""


async def _llm_chart_configs(
    columns: list[str],
    column_types: list[str],
    rows: list[dict],
    diagnostics: dict[str, dict],
    column_meanings: dict[str, str] | None = None,
) -> list[dict] | None:
    """Single unified LLM call: picks chart types grounded in real column
    semantics AND precomputed data diagnostics. Returns None on any failure
    so the caller can fall back to the rule-based generator."""
    meanings_lines = [f"- {c} ({t}): {(column_meanings or {}).get(c, 'no description')}"
                       for c, t in zip(columns, column_types)]
    prompt = CHART_SELECTION_PROMPT.format(
        max_slices=MAX_SLICE_CARDINALITY,
        column_meanings="\n".join(meanings_lines),
        diagnostics=_diagnostics_text(columns, column_types, diagnostics, row_count=len(rows)),
        sample_rows=json.dumps(rows[:3], default=str, indent=2),
    )

    raw = await call_llm(prompt, temperature=0.0)
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]
        raw = raw.rsplit("```", 1)[0].strip()
    if not raw:
        return None

    try:
        proposals = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        logger.warning("_llm_chart_configs: LLM returned invalid JSON, falling back to rule-based")
        return None
    if not isinstance(proposals, list):
        return None

    numeric_cols = [c for c, t in zip(columns, column_types)
                    if t in ("integer", "float", "decimal", "numeric", "bigint", "smallint")]

    valid: list[dict] = []
    for m in proposals:
        if not isinstance(m, dict):
            continue
        chart_type = m.get("chartType")
        x_key = m.get("xKey")
        y_keys = m.get("yKeys")
        if chart_type not in VALID_CHART_TYPES or x_key not in columns or not y_keys:
            continue
        if not all(k in columns for k in y_keys):
            continue

        if not _chart_config_is_sound(chart_type, x_key, y_keys, columns, diagnostics, rows, numeric_cols):
            logger.info("_llm_chart_configs: dropping %s (failed diagnostic validation)", chart_type)
            continue

        x_format = m.get("xFormat", "auto")
        if x_format not in ("time", "text", "number", "auto"):
            x_format = "auto"

        valid.append({
            "chartType": chart_type,
            "xKey": x_key,
            "yKeys": y_keys,
            "reason": m.get("reason", ""),
            "xLabel": _human_label(x_key),
            "yLabel": _human_label(y_keys[0]),
            "howToRead": m.get("howToRead", ""),
            "xFormat": x_format,
        })

    return valid or None


def _chart_config_is_sound(
    chart_type: str,
    x_key: str,
    y_keys: list[str],
    columns: list[str],
    diagnostics: dict[str, dict],
    rows: list[dict],
    numeric_cols: list[str],
) -> bool:
    """Re-check the LLM's chosen chart type against the precomputed diagnostics —
    a safety net in case the model ignores an INVALID-if condition."""
    x_diag = diagnostics.get(x_key, {})

    if chart_type in ("pie", "treemap", "radialBar"):
        if x_diag.get("distinct_count", 0) > MAX_SLICE_CARDINALITY:
            return False
        if x_diag.get("dominant_pct", 0) > 85:
            return False
    if chart_type == "sunburst":
        if len(y_keys) < 2:
            return False
        child_candidates = [k for k in y_keys if k not in numeric_cols and k in columns]
        if not child_candidates:
            return False
        child_col = child_candidates[0]
        if not _check_hierarchy(x_key, child_col, rows):
            return False
    if chart_type == "radar":
        if len(y_keys) < 3 or not _numeric_scale_compatible(y_keys, rows):
            return False
    if chart_type == "funnel":
        if x_diag.get("distinct_count", 0) < 2:
            return False
    if chart_type in ("scatter", "composed", "stackedArea") and len(numeric_cols) < 2:
        return False

    return True


def _pick_x_format(col: str, date_cols: list[str], cat_cols: list[str], numeric_cols: list[str]) -> str:
    if col in date_cols:
        return "time"
    if col in numeric_cols:
        return "number"
    if col in cat_cols:
        return "text"
    return "auto"


# Chart types where each row already represents one independent point and
# grouping duplicate xKey values would be meaningless or actively wrong
# (scatter plots raw correlation; sunburst already aggregates internally
# in the frontend via its own Map-based grouping).
NO_AGGREGATE_CHART_TYPES = {"scatter", "sunburst"}

# Chart types where duplicate xKey values should be averaged rather than
# summed — radar reads as a per-entity profile, not a running total, so
# summing rows that happen to share a category would inflate the shape.
MEAN_AGGREGATE_CHART_TYPES = {"radar"}


def _aggregate_chart_rows(
    chart_type: str,
    x_key: str,
    y_keys: list[str],
    rows: list[dict],
    numeric_cols: list[str],
) -> list[dict] | None:
    """If xKey has duplicate values across rows (e.g. a crosstab-shaped result
    plotted on one of its categorical columns), fold the numeric yKeys down to
    one row per xKey value — summed for totals/counts, averaged for radar's
    per-entity profile. Without this, bar/line/area/pie/radar/etc. render one
    mark per raw row instead of one per category — for wide result sets that
    means dozens of slivers (or overlapping spokes) and a fully overlapping,
    unreadable axis.
    Returns None when no aggregation is needed (already one row per xKey, or
    this chart type shouldn't be aggregated)."""
    if chart_type in NO_AGGREGATE_CHART_TYPES:
        return None
    if not x_key or not y_keys:
        return None
    sum_keys = [y for y in y_keys if y in numeric_cols]
    if not sum_keys:
        return None
    if len(set(str(r.get(x_key)) for r in rows)) == len(rows):
        return None

    sums: dict[str, dict] = {}
    counts: dict[str, int] = {}
    order: list[str] = []
    for r in rows:
        k = str(r.get(x_key))
        if k not in sums:
            sums[k] = {x_key: r.get(x_key), **{y: 0.0 for y in sum_keys}}
            counts[k] = 0
            order.append(k)
        counts[k] += 1
        for y in sum_keys:
            try:
                sums[k][y] += float(r.get(y) or 0)
            except (TypeError, ValueError):
                pass

    use_mean = chart_type in MEAN_AGGREGATE_CHART_TYPES
    result = []
    for k in order:
        row = dict(sums[k])
        if use_mean:
            n = counts[k] or 1
            for y in sum_keys:
                row[y] = row[y] / n
        result.append(row)
    return result


def _fallback_chart_configs(columns: list[str], column_types: list[str], rows: list[dict]) -> dict:
    """Rule-based: generate all valid chart types for the given data columns."""
    if not columns:
        return {"advanced": [], "basic": []}

    numeric_cols = [c for c, t in zip(columns, column_types)
                    if t in ("integer", "float", "decimal", "numeric", "bigint", "smallint")]
    date_cols = [c for c, t in zip(columns, column_types)
                 if t in ("date", "timestamp", "timestamptz")]
    cat_candidates = [c for c in columns if c not in numeric_cols]
    cat_cols = [c for c in cat_candidates if c not in date_cols]
    if not cat_cols:
        cat_cols = cat_candidates[:]

    x_key = _pick_best_x_key(date_cols + cat_cols, rows) or columns[0]
    y_keys = numeric_cols[:3] if numeric_cols else [columns[-1]]
    diagnostics = _compute_diagnostics(columns, column_types, rows)

    basic = []
    advanced = []

    basic.append({
        "chartType": "bar",
        "xKey": x_key,
        "yKeys": y_keys,
        "reason": f"Compare {_human_label(y_keys[0])} across different {_human_label(x_key)} categories",
        "xLabel": _human_label(x_key),
        "yLabel": _human_label(y_keys[0]) if y_keys else "Value",
        "howToRead": f"Look at the relative bar heights — taller means higher {_human_label(y_keys[0])}. Compare categories side by side to spot the highest and lowest values.",
        "xFormat": _pick_x_format(x_key, date_cols, cat_cols, numeric_cols),
    })
    basic.append({
        "chartType": "line",
        "xKey": x_key,
        "yKeys": y_keys,
        "reason": f"Track how {_human_label(y_keys[0])} changes over {_human_label(x_key)}",
        "xLabel": _human_label(x_key),
        "yLabel": _human_label(y_keys[0]) if y_keys else "Value",
        "howToRead": f"Follow the line trajectory over time — upward slopes mean increasing {_human_label(y_keys[0])}, downward means decreasing. Look for peaks, troughs, and trend reversals.",
        "xFormat": _pick_x_format(x_key, date_cols, cat_cols, numeric_cols),
    })
    basic.append({
        "chartType": "area",
        "xKey": x_key,
        "yKeys": y_keys,
        "reason": f"Visualize the magnitude of {_human_label(y_keys[0])} over {_human_label(x_key)}",
        "xLabel": _human_label(x_key),
        "yLabel": _human_label(y_keys[0]) if y_keys else "Value",
        "howToRead": f"The filled area emphasizes the volume of {_human_label(y_keys[0])} over time. Wider or taller sections represent higher activity or volume during that period.",
        "xFormat": _pick_x_format(x_key, date_cols, cat_cols, numeric_cols),
    })
    def first_valid_xkey(chart_type: str, candidates: list[str], yk: list[str]) -> str | None:
        for col in candidates:
            if _chart_config_is_sound(chart_type, col, yk, columns, diagnostics, rows, numeric_cols):
                return col
        return None

    if numeric_cols and cat_cols:
        pie_x = first_valid_xkey("pie", cat_cols, [numeric_cols[0]])
        if pie_x:
            basic.append({
                "chartType": "pie",
                "xKey": pie_x,
                "yKeys": [numeric_cols[0]],
                "reason": f"Show how {_human_label(numeric_cols[0])} is distributed across {_human_label(pie_x)} categories",
                "xLabel": _human_label(pie_x),
                "yLabel": _human_label(numeric_cols[0]),
                "howToRead": f"Each slice represents a {_human_label(pie_x)} category — larger slices indicate a greater share. Compare slice sizes to see which categories dominate.",
                "xFormat": _pick_x_format(pie_x, date_cols, cat_cols, numeric_cols),
            })
    if numeric_cols and cat_cols:
        treemap_x = first_valid_xkey("treemap", cat_cols, [numeric_cols[0]])
        if treemap_x:
            advanced.append({
                "chartType": "treemap",
                "xKey": treemap_x,
                "yKeys": [numeric_cols[0]],
                "reason": f"Show proportional breakdown of {_human_label(numeric_cols[0])} by {_human_label(treemap_x)} as nested rectangles",
                "xLabel": _human_label(treemap_x),
                "yLabel": _human_label(numeric_cols[0]),
                "howToRead": f"Each rectangle represents a {_human_label(treemap_x)} — the larger the area, the larger its {_human_label(numeric_cols[0])}. Compare rectangle sizes at a glance to identify the biggest contributors.",
                "xFormat": _pick_x_format(treemap_x, date_cols, cat_cols, numeric_cols),
            })
        radial_x = first_valid_xkey("radialBar", cat_cols, [numeric_cols[0]])
        if radial_x:
            advanced.append({
                "chartType": "radialBar",
                "xKey": radial_x,
                "yKeys": [numeric_cols[0]],
                "reason": f"Compare {_human_label(numeric_cols[0])} across {_human_label(radial_x)} in a circular layout",
                "xLabel": _human_label(radial_x),
                "yLabel": _human_label(numeric_cols[0]),
                "howToRead": f"Each arc represents a {_human_label(radial_x)} — the longer the arc, the higher its {_human_label(numeric_cols[0])}. The circular layout makes it easy to compare values around the ring.",
                "xFormat": _pick_x_format(radial_x, date_cols, cat_cols, numeric_cols),
            })
    if len(cat_cols) >= 2 and numeric_cols:
        sb_x = cat_cols[0]
        sb_y = [numeric_cols[0]] + cat_cols[1:3]
        if _chart_config_is_sound("sunburst", sb_x, sb_y, columns, diagnostics, rows, numeric_cols):
            advanced.append({
                "chartType": "sunburst",
                "xKey": sb_x,
                "yKeys": sb_y,
                "reason": f"Hierarchical breakdown of {_human_label(numeric_cols[0])} across {_human_label(sb_x)} and {_human_label(cat_cols[1])}",
                "xLabel": _human_label(sb_x),
                "yLabel": _human_label(numeric_cols[0]),
                "howToRead": f"The inner ring represents top-level {_human_label(sb_x)}, outer rings break down further by {_human_label(cat_cols[1])}. Compare arc sizes at each level to understand nested proportions.",
                "xFormat": _pick_x_format(sb_x, date_cols, cat_cols, numeric_cols),
            })
    if len(numeric_cols) >= 2:
        advanced.append({
            "chartType": "scatter",
            "xKey": numeric_cols[0],
            "yKeys": numeric_cols[1:3],
            "reason": f"Explore correlation between {_human_label(numeric_cols[0])} and {_human_label(numeric_cols[1])}",
            "xLabel": _human_label(numeric_cols[0]),
            "yLabel": _human_label(numeric_cols[1]),
            "howToRead": f"Each dot represents a data point — its position shows the relationship between {_human_label(numeric_cols[0])} (x-axis) and {_human_label(numeric_cols[1])} (y-axis). Clusters, trends, and outliers are easy to spot.",
            "xFormat": _pick_x_format(numeric_cols[0], date_cols, cat_cols, numeric_cols),
        })
        advanced.append({
            "chartType": "composed",
            "xKey": x_key,
            "yKeys": numeric_cols[:3],
            "reason": f"Multi-metric view — bars for {_human_label(numeric_cols[0])} with trend lines for other metrics",
            "xLabel": _human_label(x_key),
            "yLabel": _human_label(numeric_cols[0]),
            "howToRead": f"Bars show {_human_label(numeric_cols[0])} over time, while overlaid lines show trends in other metrics. This combined view reveals how multiple measures move together or diverge.",
            "xFormat": _pick_x_format(x_key, date_cols, cat_cols, numeric_cols),
        })
        advanced.append({
            "chartType": "stackedArea",
            "xKey": x_key,
            "yKeys": numeric_cols[:3],
            "reason": f"Stacked view of how multiple metrics contribute to the total over {_human_label(x_key)}",
            "xLabel": _human_label(x_key),
            "yLabel": _human_label(numeric_cols[0]),
            "howToRead": f"Each colored layer represents a different metric — the total height shows the combined value. Watch how layers grow or shrink over time to see shifting contributions.",
            "xFormat": _pick_x_format(x_key, date_cols, cat_cols, numeric_cols),
        })
    if cat_cols and len(numeric_cols) >= 3:
        cat_x = _pick_best_x_key(cat_cols, rows)
        if _chart_config_is_sound("radar", cat_x, numeric_cols[:6], columns, diagnostics, rows, numeric_cols):
            advanced.append({
                "chartType": "radar",
                "xKey": cat_x,
                "yKeys": numeric_cols[:6],
                "reason": f"Multi-dimensional profile comparing {_human_label(cat_x)} across {len(numeric_cols[:6])} metrics",
                "xLabel": _human_label(cat_x),
                "yLabel": _human_label(numeric_cols[0]),
                "howToRead": f"Each spoke represents a metric — the further from center, the higher the value. Compare polygon shapes across different {_human_label(cat_x)} to identify strengths and weaknesses in each profile.",
                "xFormat": _pick_x_format(cat_x, date_cols, cat_cols, numeric_cols),
            })
    if len(cat_cols) >= 1 and numeric_cols and len(rows) >= 2:
        funnel_x = first_valid_xkey("funnel", cat_cols, [numeric_cols[0]])
        if funnel_x:
            advanced.append({
                "chartType": "funnel",
                "xKey": funnel_x,
                "yKeys": [numeric_cols[0]],
                "reason": f"Show progression or drop-off across {_human_label(funnel_x)} stages",
                "xLabel": _human_label(funnel_x),
                "yLabel": _human_label(numeric_cols[0]),
                "howToRead": f"Each funnel stage represents a step in the progression — narrower sections indicate drop-off. Compare adjacent stages to see where the largest decline happens.",
                "xFormat": _pick_x_format(funnel_x, date_cols, cat_cols, numeric_cols),
            })

    return {"advanced": advanced, "basic": basic}


def _pivot_data(
    columns: list[str],
    column_types: list[str],
    rows: list[dict],
) -> dict | None:
    """Detect crosstab (exactly 2 cat + 1 numeric column) and pivot long → wide.
    Returns {"columns": [...], "rows": [...], "xKey": "...", "yKeys": [...]} or None."""
    numeric_cols = [c for c, t in zip(columns, column_types)
                    if t in ("integer", "float", "decimal", "numeric", "bigint", "smallint")]
    date_cols = [c for c, t in zip(columns, column_types)
                 if t in ("date", "timestamp", "timestamptz")]
    cat_candidates = [c for c in columns if c not in numeric_cols]
    cat_cols = [c for c in cat_candidates if c not in date_cols]

    all_cat = list(dict.fromkeys(cat_cols + date_cols))
    if len(all_cat) != 2 or len(numeric_cols) != 1:
        return None

    value_col = numeric_cols[0]

    if date_cols:
        x_key = date_cols[0]
        spread_col = [c for c in all_cat if c != x_key][0]
    else:
        distinct_counts = {}
        for c in all_cat:
            distinct_counts[c] = len(set(str(r.get(c, "")) for r in rows))
        if distinct_counts[all_cat[0]] >= distinct_counts[all_cat[1]]:
            x_key = all_cat[0]
            spread_col = all_cat[1]
        else:
            x_key = all_cat[1]
            spread_col = all_cat[0]

    spread_vals = sorted(set(str(r.get(spread_col, "")) for r in rows if r.get(spread_col)))
    if len(spread_vals) > MAX_SLICE_CARDINALITY:
        return None

    grouped: dict[str, dict] = {}
    for r in rows:
        x_val = str(r.get(x_key, ""))
        s_val = str(r.get(spread_col, ""))
        v = r.get(value_col, 0)
        if x_val not in grouped:
            grouped[x_val] = {x_key: x_val}
        try:
            grouped[x_val][s_val] = float(v) if v is not None else 0
        except (TypeError, ValueError):
            grouped[x_val][s_val] = 0

    new_columns = [x_key] + spread_vals
    new_rows = list(grouped.values())

    return {
        "columns": new_columns,
        "rows": new_rows,
        "xKey": x_key,
        "yKeys": spread_vals,
    }


def _crosstab_chart_configs(
    columns: list[str],
    column_types: list[str],
    rows: list[dict],
) -> list[dict]:
    """Generate grouped bar + line chart configs for crosstab data.
    Returns chart config dicts with embedded pivoted rows."""
    pivoted = _pivot_data(columns, column_types, rows)
    if not pivoted:
        return []

    x_key = pivoted["xKey"]
    y_keys = pivoted["yKeys"]
    p_rows = pivoted["rows"]

    date_cols = [c for c, t in zip(columns, column_types)
                 if t in ("date", "timestamp", "timestamptz")]
    numeric_cols = [c for c, t in zip(columns, column_types)
                    if t in ("integer", "float", "decimal", "numeric", "bigint", "smallint")]
    cat_candidates = [c for c in columns if c not in numeric_cols]
    cat_cols = [c for c in cat_candidates if c not in date_cols]

    x_format = _pick_x_format(x_key, date_cols, cat_cols, numeric_cols)

    n_cats = len(y_keys)
    return [
        {
            "chartType": "bar",
            "xKey": x_key,
            "yKeys": y_keys,
            "reason": f"Grouped bar — {n_cats} categories, each bar color shows a different category breakdown across {_human_label(x_key)}",
            "xLabel": _human_label(x_key),
            "yLabel": _human_label(numeric_cols[0]) if numeric_cols else "Count",
            "howToRead": f"Each group of bars along the x-axis represents a {_human_label(x_key)} value. Different bar colors represent different categories — compare bar heights within each group to see composition, and follow a single color across groups to see trends over time.",
            "xFormat": x_format,
            "rows": p_rows,
        },
    ]


EXTRACT_ACTIONS_PROMPT = """Extract exactly 5 interactive analysis actions from the response text below. Return ONLY a JSON array — no markdown, no code fences.
{language_instruction}

Each object in the array must have:
- "name": short actionable label (e.g., "Compare quality scores by supplier")
- "description": natural paragraph (3-4 sentences) explaining what this analysis reveals, including which columns are examined and what insight to expect — extract the full text from the source without truncation
- "datasets": list of dataset names to use — ONLY from this allowed list: {datasets}
- "goal" (optional): one-sentence purpose of this analysis (what it aims to find out)
- "columns" (optional): list of specific column names examined in this analysis
- "insight" (optional): what insight or finding the user can expect from this analysis

IMPORTANT: The "name", "description", "goal", and "insight" fields MUST be written in the language indicated above.

If no clear actions, return [].

Text:
{text}"""


async def extract_analysis_actions(text: str, dataset_names: list[str], language: str = "en") -> list[dict]:
    """Extract interactive analysis action proposals from a chat response text."""
    if not text.strip():
        return []

    prompt = EXTRACT_ACTIONS_PROMPT.format(text=text[:8000], datasets=json.dumps(dataset_names), language_instruction=language_instruction(language))
    try:
        raw = (await call_llm(prompt, language=language)).strip()
        if not raw:
            return []
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1]
            raw = raw.rsplit("```", 1)[0]
        actions = json.loads(raw)
        if not isinstance(actions, list):
            return []
        real = set(dataset_names)
        for a in actions:
            if isinstance(a, str):
                a = {"name": a, "description": "", "datasets": dataset_names}
            if "datasets" not in a or not a["datasets"]:
                a["datasets"] = dataset_names
            elif real:
                a["datasets"] = [d for d in a["datasets"] if d in real] or dataset_names
            if "description" not in a:
                a["description"] = ""
        return actions[:5]
    except (json.JSONDecodeError, Exception) as e:
        logger.warning(f"extract_analysis_actions: failed — {e}")
        return []


EXTRACT_AIMS_PROMPT = """Extract specific analysis aims from the research text below. Return ONLY a JSON array — no markdown, no code fences.

Each object in the array must have:
- "aim": short name (2-6 words)
- "description": what this analysis computes or reveals (1 sentence)
- "datasets": list of dataset names to use
- "goal" (optional): one-sentence purpose of this analysis
- "columns" (optional): list of specific column names examined
- "insight" (optional): what insight or finding the user can expect

If no clear aims, return [].

Text:
{text}"""


GENERATE_AIM_PROMPT = """You are a data analysis strategist. Based on the user's request and the available datasets, propose ONE structured analysis aim.

## Available Datasets
{context}

## User Request
{user_text}

## Instructions
Respond with a JSON object (no markdown, no code fences) with these fields:
- "aim": Short, clear title for the analysis (10 words max)
- "how_we_will_do_it": Step-by-step description of the analysis approach (2-3 sentences)
- "datasets_used": List of dataset names that are needed
- "joins": Description of how datasets are joined, or null if only one dataset is needed

## Rules
- Only use datasets, tables, and columns from the available datasets above
- Be specific about which columns and metrics will be analyzed
- Keep "how_we_will_do_it" actionable and concrete"""


async def generate_aim(user_text: str, datasets: list[dict]) -> dict:
    """LLM generates a structured analysis aim from user text + selected datasets."""
    context = build_dataset_context(datasets)
    prompt = GENERATE_AIM_PROMPT.format(context=context, user_text=user_text)
    raw = await call_llm(prompt)
    if not raw:
        return {"aim": "", "how_we_will_do_it": "", "datasets_used": [d.get("dataset_name", "?") for d in datasets], "joins": None}
    # Strip markdown code fences if present
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]
        raw = raw.rsplit("```", 1)[0]
    try:
        result = json.loads(raw)
        if not isinstance(result, dict):
            raise ValueError("response is not a dict")
        return {
            "aim": str(result.get("aim", ""))[:60],
            "how_we_will_do_it": str(result.get("how_we_will_do_it", ""))[:500],
            "datasets_used": result.get("datasets_used", [d.get("dataset_name", "?") for d in datasets]),
            "joins": result.get("joins"),
        }
    except (json.JSONDecodeError, Exception) as e:
        logger.warning(f"generate_aim: failed to parse LLM response — {e}")
        return {"aim": "", "how_we_will_do_it": "", "datasets_used": [d.get("dataset_name", "?") for d in datasets], "joins": None}


async def extract_aims_from_text(text: str, dataset_names: list[str]) -> list[dict]:
    """Extract structured aim proposals from a chat response text."""
    if not text.strip():
        return []

    prompt = EXTRACT_AIMS_PROMPT.format(text=text[:8000])
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
