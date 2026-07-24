"""LLM service — chat responses and aim generation."""

import json
import logging
from config import get_settings, get_llm_client
from sql_executor import explain_sql, validate_sql, validate_sql_safety, clean_sql
from llm_client import build_enrichment_system_prompt

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


async def call_llm(prompt: str) -> str:
    """Simple LLM call returning text response."""
    settings = get_settings()
    client = get_llm_client()
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

    # Add LIMIT if missing (validate_sql does this) before safety check
    try:
        validated = validate_sql(cleaned)
    except ValueError as e:
        return {"pass": False, "issues": [str(e)[:300]], "suggestions": "Fix the validation error"}

    # 1. Syntax check via EXPLAIN
    try:
        await explain_sql(validated)
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
    )
    return response.choices[0].message.content or ""


async def generate_chat_response(
    message: str,
    dataset_names: list[str],
    datasets_data: list[dict],
    history: list[dict] | None = None,
    enrichment_block: str | None = None,
    enrichment_mode: str = "",
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
            system_prompt = build_enrichment_system_prompt(enrichment_mode, context)
            combined_system = f"{system_prompt}\n\n## Previous Context\n{enrichment_block}"
            messages = [
                {"role": "system", "content": combined_system},
                {"role": "user", "content": message},
            ]
        else:
            system_prompt = CHAT_SYSTEM_PROMPT.replace("{context}", context)
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

CHART_SELECTION_PROMPT = """You are a data visualization expert. Given the schema and sample data below, recommend charts that each reveal a unique insight.

## Supported Chart Types
ADVANCED (shown prominently above basic charts — prefer these when data supports multi-dimensional or mixed views):
- "composed": mixed views — stacked bars with a trend line overlay (needs 2+ numeric yKeys)
- "stackedArea": volume over time with multiple series stacked (needs 2+ numeric yKeys + time/category xKey)
- "treemap": proportional breakdown by category (needs 1 category + 1 numeric value)
- "radialBar": circular multi-metric comparison (needs 1 category + 1+ numeric values)
- "funnel": conversion or drop-off pipeline (needs 1 stage/label column + 1 numeric value)
- "sunburst": hierarchical nested categories (needs 2+ category columns + 1 numeric value)
- "scatter": correlation between two numeric variables (needs 2+ numeric columns)
- "radar": multi-dimensional comparison profiles (needs 1 label + 2+ numeric metrics)

BASIC (always available):
- "bar": comparing categories or groups
- "line": trends over time or ordered sequences
- "area": volume/magnitude over time (filled line)
- "pie": proportions of a whole (max 8 slices)

## Decision Guide
- If data has 2+ numeric columns → MUST include at least one of: composed, stackedArea, scatter, radar
- If data has 1 category + 1 numeric → consider treemap or funnel or radialBar
- If data has 2+ category columns + 1 numeric → consider sunburst
- If data looks like stages/pipeline → consider funnel
- Always return 1-2 ADVANCED and 2-3 BASIC charts

## Column Schema
{column_schema}

## Sample Data (first {sample_count} rows)
{sample_data}

## Rules
- Return 1-2 ADVANCED chart types if the data supports multi-dimensional or mixed views
- Return 2-3 BASIC chart types — always include these
- Each chart must reveal a DIFFERENT perspective on the same data
- Validate all referenced columns exist in the schema
- Return ONLY valid JSON — no markdown, no code fences

## Output Format
{{
  "advanced": [
    {{
      "chartType": "composed|stackedArea|treemap|radialBar|funnel|sunburst|scatter|radar",
      "xKey": "<column for x-axis>",
      "yKeys": ["<columns for y-axis>"],
      "reason": "<1-sentence: what insight this chart reveals>",
      "xLabel": "<human-readable x-axis label, e.g. 'Supplier' or 'Month'>",
      "yLabel": "<human-readable y-axis label, e.g. 'Average Score' or 'Revenue ($)'>",
      "howToRead": "<1-2 sentences of general reading guidance: typical value ranges, what's notable, what to look for — NOT exact analysis of the specific numbers>"
    }}
  ],
  "basic": [
    {{
      "chartType": "bar|line|area|pie",
      "xKey": "<column for x-axis>",
      "yKeys": ["<columns for y-axis>"],
      "reason": "<1-sentence: what insight this chart reveals>",
      "xLabel": "<human-readable x-axis label>",
      "yLabel": "<human-readable y-axis label>",
      "howToRead": "<1-2 sentences of general reading guidance>"
    }}
  ]
}}"""


CHART_RETRY_PROMPT = """Your previous chart configuration was invalid.

Error: {error_message}
Column schema: {column_schema}
Your previous response: {previous_response}

Please fix the issues above and return a valid JSON object with "advanced" and "basic" arrays.
Common fixes:
- chartType must be one of: composed, stackedArea, treemap, radialBar, funnel, sunburst, scatter, radar, bar, line, area, pie
- xKey and yKeys must reference exact column names from the schema
- Each chart must have a "reason" field explaining the insight
- Each chart must have "xLabel" and "yLabel" (human-readable axis labels)
- Each chart must have "howToRead" (1-2 sentences of general reading guidance)
- advanced and basic must be arrays (use [] if none)"""


VALID_CHART_TYPES = {"composed", "stackedArea", "treemap", "radialBar", "funnel", "sunburst", "scatter", "radar",
                     "bar", "line", "area", "pie"}


def _validate_chart_config(cfg: dict, columns: list[str]) -> bool:
    """Validate a single chart config has valid type, column references, and labels."""
    if not isinstance(cfg, dict):
        return False
    if cfg.get("chartType") not in VALID_CHART_TYPES:
        return False
    if not cfg.get("xKey") or not isinstance(cfg.get("yKeys"), list):
        return False
    if cfg["xKey"] not in columns:
        return False
    if not all(yk in columns for yk in cfg["yKeys"]):
        return False
    if not cfg.get("xLabel") or not isinstance(cfg.get("xLabel"), str):
        cfg["xLabel"] = cfg["xKey"].replace("_", " ").title()
    if not cfg.get("yLabel") or not isinstance(cfg.get("yLabel"), str):
        cfg["yLabel"] = (cfg["yKeys"][0] if cfg["yKeys"] else "Value").replace("_", " ").title()
    if not cfg.get("howToRead") or not isinstance(cfg.get("howToRead"), str):
        cfg["howToRead"] = ""
    return True


def _fallback_chart_configs(columns: list[str], column_types: list[str], rows: list[dict]) -> dict:
    """Rule-based fallback: generate basic + advanced charts when LLM fails."""
    numeric_cols = [c for c, t in zip(columns, column_types)
                    if t in ("integer", "float", "decimal", "numeric", "bigint", "smallint")]
    date_cols = [c for c, t in zip(columns, column_types)
                 if t in ("date", "timestamp", "timestamptz")]
    x_key = date_cols[0] if date_cols else columns[0]
    y_keys = numeric_cols[:3] if numeric_cols else [columns[-1]]

    def _human_label(col: str) -> str:
        return col.replace("_", " ").title()

    basic = [
        {"chartType": "bar", "xKey": x_key, "yKeys": y_keys, "reason": "Compare values across categories",
         "xLabel": _human_label(x_key), "yLabel": _human_label(y_keys[0]) if y_keys else "Value", "howToRead": ""},
    ]
    if date_cols:
        basic.append({"chartType": "line", "xKey": x_key, "yKeys": y_keys, "reason": "Show trends over time",
                      "xLabel": _human_label(x_key), "yLabel": _human_label(y_keys[0]) if y_keys else "Value", "howToRead": ""})
        basic.append({"chartType": "area", "xKey": x_key, "yKeys": y_keys, "reason": "Show volume over time",
                      "xLabel": _human_label(x_key), "yLabel": _human_label(y_keys[0]) if y_keys else "Value", "howToRead": ""})
    if len(numeric_cols) == 1 and len(columns) >= 2:
        pie_x = columns[0] if columns[0] != numeric_cols[0] else columns[-1]
        basic.append({"chartType": "pie", "xKey": pie_x, "yKeys": [numeric_cols[0]], "reason": "Show proportional distribution",
                      "xLabel": _human_label(pie_x), "yLabel": _human_label(numeric_cols[0]), "howToRead": ""})

    advanced = []
    if len(numeric_cols) >= 2:
        advanced.append({
            "chartType": "stackedArea",
            "xKey": x_key,
            "yKeys": numeric_cols[:3],
            "reason": "Compare volume trends across multiple metrics",
            "xLabel": _human_label(x_key), "yLabel": _human_label(numeric_cols[0]), "howToRead": ""
        })
        if date_cols:
            advanced.append({
                "chartType": "composed",
                "xKey": x_key,
                "yKeys": numeric_cols[:3],
                "reason": "Mixed view: stacked bars with trend overlay",
                "xLabel": _human_label(x_key), "yLabel": _human_label(numeric_cols[0]), "howToRead": ""
            })
    if len(numeric_cols) >= 1 and len(columns) >= 3:
        cat_cols = [c for c in columns if c not in numeric_cols]
        if len(cat_cols) >= 2:
            advanced.append({
                "chartType": "sunburst",
                "xKey": cat_cols[0],
                "yKeys": [numeric_cols[0]],
                "reason": "Hierarchical breakdown across nested categories",
                "xLabel": _human_label(cat_cols[0]), "yLabel": _human_label(numeric_cols[0]), "howToRead": ""
            })

    return {"advanced": advanced[:2], "basic": basic}


async def suggest_charts(
    columns: list[str],
    column_types: list[str],
    rows: list[dict],
    max_retries: int = 2,
) -> dict:
    """Call LLM to recommend chart types for result data.

    Returns: {"advanced": [...], "basic": [...]}
    Retries up to max_retries times on invalid output.
    Falls back to rule-based defaults on persistent failure.
    """
    if not columns or not rows:
        return _fallback_chart_configs(columns, column_types, rows)

    # Build schema string
    type_lookup = dict(zip(columns, column_types))
    schema_lines = []
    for col in columns:
        t = type_lookup.get(col, "text")
        schema_lines.append(f"- {col} ({t})")
    column_schema = "\n".join(schema_lines)

    # Sample first 5 rows
    sample = rows[:5]
    sample_str = json.dumps(sample, default=str, indent=2)

    prompt = CHART_SELECTION_PROMPT.format(
        column_schema=column_schema,
        sample_count=len(sample),
        sample_data=sample_str,
    )

    last_error = None
    for attempt in range(max_retries + 1):
        raw = await call_llm(prompt)
        raw = raw.strip()

        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1]
            raw = raw.rsplit("```", 1)[0].strip()

        try:
            result = json.loads(raw)
            if not isinstance(result, dict):
                raise ValueError("Response is not a JSON object")

            advanced = result.get("advanced", [])
            basic = result.get("basic", [])

            if not isinstance(advanced, list) or not isinstance(basic, list):
                raise ValueError("advanced and basic must be arrays")

            valid_advanced = [c for c in advanced if _validate_chart_config(c, columns)]
            valid_basic = [c for c in basic if _validate_chart_config(c, columns)]

            if len(valid_basic) >= 1:
                return {"advanced": valid_advanced[:2], "basic": valid_basic[:3]}

            raise ValueError("No valid basic chart configs found")

        except (json.JSONDecodeError, ValueError) as e:
            last_error = str(e)
            logger.warning("suggest_charts attempt %d/%d failed: %s", attempt + 1, max_retries + 1, e)
            if attempt < max_retries:
                prompt = (
                    CHART_RETRY_PROMPT.format(
                        error_message=last_error,
                        column_schema=column_schema,
                        previous_response=raw[:1000],
                    )
                    + f"\n\n## Column Schema\n{column_schema}\n\n## Sample Data\n{sample_str}"
                )

    logger.warning("suggest_charts all attempts failed, using fallback: %s", last_error)
    return _fallback_chart_configs(columns, column_types, rows)


EXTRACT_ACTIONS_PROMPT = """Extract exactly 5 interactive analysis actions from the response text below. Return ONLY a JSON array — no markdown, no code fences.

Each object in the array must have:
- "name": short actionable label (e.g., "Compare quality scores by supplier")
- "description": what this analysis reveals (1 sentence)
- "datasets": list of dataset names to use

If no clear actions, return [].

Text:
{text}"""


async def extract_analysis_actions(text: str, dataset_names: list[str]) -> list[dict]:
    """Extract interactive analysis action proposals from a chat response text."""
    if not text.strip():
        return []

    prompt = EXTRACT_ACTIONS_PROMPT.format(text=text[:2000])
    try:
        raw = (await call_llm(prompt)).strip()
        if not raw:
            return []
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1]
            raw = raw.rsplit("```", 1)[0]
        actions = json.loads(raw)
        if not isinstance(actions, list):
            return []
        for a in actions:
            if isinstance(a, str):
                a = {"name": a, "description": "", "datasets": dataset_names}
            if "datasets" not in a or not a["datasets"]:
                a["datasets"] = dataset_names
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
