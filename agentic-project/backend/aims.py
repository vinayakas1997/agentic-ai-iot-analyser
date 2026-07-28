"""LLM service — chat responses and aim generation."""

import json
import logging
from config import get_settings, get_llm_client
from sql_executor import explain_sql, validate_sql, validate_sql_safety, clean_sql
from llm_client import build_enrichment_system_prompt, language_instruction

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


def _column_distinct_profile(columns: list[str], column_types: list[str], rows: list[dict]) -> str:
    """Build: column name | type | distinct count | first 5 sample values."""
    type_map = dict(zip(columns, column_types))
    lines = []
    for col in columns:
        t = type_map.get(col, "text")
        seen: list[str] = []
        seen_set: set[str] = set()
        for r in rows:
            v = str(r.get(col, ""))
            if v not in seen_set:
                seen_set.add(v)
                seen.append(v)
            if len(seen) >= 5:
                break
        vals_display = ", ".join(repr(v) for v in seen)
        lines.append(f"- {col} ({t}, {len(seen_set)} distinct): {vals_display}")
    return "\n".join(lines)


MULTI_DIM_PROMPT = """You are a data visualization expert. Given the column profile and sample data below, recommend xKey and yKeys for each compatible multi-dim chart type.

## Column Profile (name | type | distinct count | sample values)
{column_profile}

## Sample Rows (first 3)
{sample_rows}

## Chart Types & Requirements
- **composed**: mixed bars + line overlay — needs 1 category/date xKey + 2+ numeric yKeys (last yKey becomes the line)
- **stackedArea**: stacked volumes — needs 1 category/date xKey + 2+ numeric yKeys
- **sunburst**: nested hierarchy — needs 1 top-level category xKey + yKeys must be [numeric_value, sub_category_1, sub_category_2, ...]
- Set a chart type to null if the data doesn't support it
- xKey should be the most meaningful axis (date or category with many distinct values)
- yKeys must reference existing column names exactly
- Each chart needs a unique 1-sentence "reason" explaining the insight

## Output Format — JSON only, no markdown, no code fences
{{
  "composed": {{"xKey": "...", "yKeys": [...], "reason": "..."}} | null,
  "stackedArea": {{"xKey": "...", "yKeys": [...], "reason": "..."}} | null,
  "sunburst": {{"xKey": "...", "yKeys": [...], "reason": "..."}} | null
}}"""


async def _enrich_multi_dim_configs(
    columns: list[str],
    column_types: list[str],
    rows: list[dict],
    configs: dict,
) -> dict:
    """Batch LLM call to improve xKey/yKeys for composed, stackedArea, sunburst.
    Falls back to original configs on failure."""
    existing = {c["chartType"]: c for c in configs.get("advanced", [])
                if c["chartType"] in ("composed", "stackedArea", "sunburst")}
    if not existing:
        return configs

    profile = _column_distinct_profile(columns, column_types, rows)
    sample = json.dumps(rows[:3], default=str, indent=2)
    prompt = MULTI_DIM_PROMPT.format(column_profile=profile, sample_rows=sample)

    raw = await call_llm(prompt)
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]
        raw = raw.rsplit("```", 1)[0].strip()

    try:
        mapping = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        logger.warning("_enrich_multi_dim_configs: LLM returned invalid JSON, keeping defaults")
        return configs

    for chart_type, m in mapping.items():
        if m is None or chart_type not in existing:
            continue
        if not isinstance(m, dict):
            continue
        if m.get("xKey") not in columns or not m.get("yKeys"):
            continue
        if not all(k in columns for k in m["yKeys"]):
            continue
        existing[chart_type].update({
            "xKey": m["xKey"],
            "yKeys": m["yKeys"],
            "reason": m.get("reason", existing[chart_type]["reason"]),
            "xLabel": _human_label(m["xKey"]),
            "yLabel": _human_label(m["yKeys"][0]) if m["yKeys"] else existing[chart_type]["yLabel"],
        })

    return configs


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
    })
    basic.append({
        "chartType": "line",
        "xKey": x_key,
        "yKeys": y_keys,
        "reason": f"Track how {_human_label(y_keys[0])} changes over {_human_label(x_key)}",
        "xLabel": _human_label(x_key),
        "yLabel": _human_label(y_keys[0]) if y_keys else "Value",
        "howToRead": f"Follow the line trajectory over time — upward slopes mean increasing {_human_label(y_keys[0])}, downward means decreasing. Look for peaks, troughs, and trend reversals.",
    })
    basic.append({
        "chartType": "area",
        "xKey": x_key,
        "yKeys": y_keys,
        "reason": f"Visualize the magnitude of {_human_label(y_keys[0])} over {_human_label(x_key)}",
        "xLabel": _human_label(x_key),
        "yLabel": _human_label(y_keys[0]) if y_keys else "Value",
        "howToRead": f"The filled area emphasizes the volume of {_human_label(y_keys[0])} over time. Wider or taller sections represent higher activity or volume during that period.",
    })
    if numeric_cols and cat_cols:
        pie_x = _pick_best_x_key(cat_cols, rows)
        basic.append({
            "chartType": "pie",
            "xKey": pie_x,
            "yKeys": [numeric_cols[0]],
            "reason": f"Show how {_human_label(numeric_cols[0])} is distributed across {_human_label(pie_x)} categories",
            "xLabel": _human_label(pie_x),
            "yLabel": _human_label(numeric_cols[0]),
            "howToRead": f"Each slice represents a {_human_label(pie_x)} category — larger slices indicate a greater share. Compare slice sizes to see which categories dominate.",
        })
    if numeric_cols and cat_cols:
        cat_x = _pick_best_x_key(cat_cols, rows)
        advanced.append({
            "chartType": "treemap",
            "xKey": cat_x,
            "yKeys": [numeric_cols[0]],
            "reason": f"Show proportional breakdown of {_human_label(numeric_cols[0])} by {_human_label(cat_x)} as nested rectangles",
            "xLabel": _human_label(cat_x),
            "yLabel": _human_label(numeric_cols[0]),
            "howToRead": f"Each rectangle represents a {_human_label(cat_x)} — the larger the area, the larger its {_human_label(numeric_cols[0])}. Compare rectangle sizes at a glance to identify the biggest contributors.",
        })
        advanced.append({
            "chartType": "radialBar",
            "xKey": cat_x,
            "yKeys": [numeric_cols[0]],
            "reason": f"Compare {_human_label(numeric_cols[0])} across {_human_label(cat_x)} in a circular layout",
            "xLabel": _human_label(cat_x),
            "yLabel": _human_label(numeric_cols[0]),
            "howToRead": f"Each arc represents a {_human_label(cat_x)} — the longer the arc, the higher its {_human_label(numeric_cols[0])}. The circular layout makes it easy to compare values around the ring.",
        })
    if len(cat_cols) >= 2 and numeric_cols:
        advanced.append({
            "chartType": "sunburst",
            "xKey": cat_cols[0],
            "yKeys": [numeric_cols[0]] + cat_cols[1:3],
            "reason": f"Hierarchical breakdown of {_human_label(numeric_cols[0])} across {_human_label(cat_cols[0])} and {_human_label(cat_cols[1])}",
            "xLabel": _human_label(cat_cols[0]),
            "yLabel": _human_label(numeric_cols[0]),
            "howToRead": f"The inner ring represents top-level {_human_label(cat_cols[0])}, outer rings break down further by {_human_label(cat_cols[1])}. Compare arc sizes at each level to understand nested proportions.",
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
        })
        advanced.append({
            "chartType": "composed",
            "xKey": x_key,
            "yKeys": numeric_cols[:3],
            "reason": f"Multi-metric view — bars for {_human_label(numeric_cols[0])} with trend lines for other metrics",
            "xLabel": _human_label(x_key),
            "yLabel": _human_label(numeric_cols[0]),
            "howToRead": f"Bars show {_human_label(numeric_cols[0])} over time, while overlaid lines show trends in other metrics. This combined view reveals how multiple measures move together or diverge.",
        })
        advanced.append({
            "chartType": "stackedArea",
            "xKey": x_key,
            "yKeys": numeric_cols[:3],
            "reason": f"Stacked view of how multiple metrics contribute to the total over {_human_label(x_key)}",
            "xLabel": _human_label(x_key),
            "yLabel": _human_label(numeric_cols[0]),
            "howToRead": f"Each colored layer represents a different metric — the total height shows the combined value. Watch how layers grow or shrink over time to see shifting contributions.",
        })
    if cat_cols and len(numeric_cols) >= 3:
        cat_x = _pick_best_x_key(cat_cols, rows)
        advanced.append({
            "chartType": "radar",
            "xKey": cat_x,
            "yKeys": numeric_cols[:6],
            "reason": f"Multi-dimensional profile comparing {_human_label(cat_x)} across {len(numeric_cols[:6])} metrics",
            "xLabel": _human_label(cat_x),
            "yLabel": _human_label(numeric_cols[0]),
            "howToRead": f"Each spoke represents a metric — the further from center, the higher the value. Compare polygon shapes across different {_human_label(cat_x)} to identify strengths and weaknesses in each profile.",
        })
    if len(cat_cols) >= 1 and numeric_cols and len(rows) >= 2:
        cat_x = _pick_best_x_key(cat_cols, rows)
        advanced.append({
            "chartType": "funnel",
            "xKey": cat_x,
            "yKeys": [numeric_cols[0]],
            "reason": f"Show progression or drop-off across {_human_label(cat_x)} stages",
            "xLabel": _human_label(cat_x),
            "yLabel": _human_label(numeric_cols[0]),
            "howToRead": f"Each funnel stage represents a step in the progression — narrower sections indicate drop-off. Compare adjacent stages to see where the largest decline happens.",
        })

    return {"advanced": advanced, "basic": basic}


EXTRACT_ACTIONS_PROMPT = """Extract exactly 5 interactive analysis actions from the response text below. Return ONLY a JSON array — no markdown, no code fences.

Each object in the array must have:
- "name": short actionable label (e.g., "Compare quality scores by supplier")
- "description": natural paragraph (3-4 sentences) explaining what this analysis reveals, including which columns are examined and what insight to expect — extract the full text from the source without truncation
- "datasets": list of dataset names to use — ONLY from this allowed list: {datasets}

If no clear actions, return [].

Text:
{text}"""


async def extract_analysis_actions(text: str, dataset_names: list[str]) -> list[dict]:
    """Extract interactive analysis action proposals from a chat response text."""
    if not text.strip():
        return []

    prompt = EXTRACT_ACTIONS_PROMPT.format(text=text[:8000], datasets=json.dumps(dataset_names))
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
