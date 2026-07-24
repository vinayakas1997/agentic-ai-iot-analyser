"""LLM client — summary generation, mode-specific prompts, and agentic research routing."""

import logging
import re
import time
from config import get_settings, get_llm_client
from logger import log_route, log_llm_call, log_sql, log_full_prompt

logger = logging.getLogger(__name__)

SUMMARIZE_PROMPT = """Summarize the following conversation thread in 2-3 sentences.
Focus on: what analysis was done, what data was used (datasets + SQL queries), and key findings.

{thread_text}
"""

ENRICHMENT_INSTRUCTION = """
INTERPRET THE CONTEXT BELOW:
The context shows previous analysis work in this session. Each section is labeled with the
aim or dataset it relates to. "[Summary: ...]" entries are compressed history of multiple turns.
"[Turn]" entries are individual interactions with their SQL and row counts.

IMPORTANT: The context is filtered — it only shows what's relevant to your currently attached
aims and datasets. If you need information about something not shown, attach it first.
"""

# ── Route Prompts ──

ROUTER_PROMPT = """Classify the user's question into one of these categories:

1. DIRECT — User asks a specific factual question (e.g., "which fruit has the highest sale?", "what is the average cost?", "show me sales by region"). The question can be answered with a single SQL query.

2. SUGGEST — User explores possibilities (e.g., "what can I do?", "what analyses are possible?", "give me ideas", "explain", "describe the data", "tell me about the data"). No specific question, just looking for direction.

3. FOCUS — User wants to deep-dive on one specific analysis topic (e.g., "tell me more about quality impact", "elaborate on sales trends", "go deeper into this analysis").

4. DEEP — User wants comprehensive research or a full analysis (e.g., "analyze everything", "do a full analysis of sales", "research this topic thoroughly", "give me a complete picture"). Requires multiple queries to build a complete understanding.

User question: {question}

Respond with ONLY the category name: DIRECT, SUGGEST, FOCUS, or DEEP."""

DIRECT_PROMPT = """You are a data analysis assistant. Current mode: RESEARCH — DIRECT ANSWER.

The user asked a specific factual question. You MUST generate a SQL query to answer it.

## Available Datasets
{context}
{enrichment_instruction}

## Instructions
1. Write a SQL query that directly answers the user's question
2. Wrap the SQL in a ```sql code block so the system can extract and execute it
3. After the SQL, explain what the query does (1-2 sentences)

## CRITICAL RULES
- You MUST output a SQL query in a ```sql code block. This is REQUIRED.
- Do NOT output numbered analysis suggestions or exploration ideas — that is SUGGEST mode.
- Do NOT output "Here are 3 ideas..." or numbered lists — that is WRONG for DIRECT mode.
- If the question is ambiguous and you cannot write SQL, respond with exactly: NONE

## SQL Rules
- Only use columns and tables from the datasets above
- Always include LIMIT 100 unless the user asks for all results
- Use explicit JOIN conditions when combining datasets
"""

SUGGEST_PROMPT = """You are a data analysis assistant. Current mode: RESEARCH — SUGGEST IDEAS.

The user is exploring what analyses are possible with their data. Start with a brief conversational opening acknowledging their question, then list exactly 3 numbered analysis suggestions.

## Available Datasets
{context}
{enrichment_instruction}

## Instructions
Start with 1-2 sentences of conversational text acknowledging the user's question (e.g. "Great question — here are 3 ways to explore your data:"), then output exactly 3 numbered suggestions. Use **bold** around field names and put each field on its own line:

1. **Name**: Short, clear title
   **Goal**: What insight this analysis would reveal
   **Datasets**: fruits, fruit_quality
   **Columns**: fruits_name, quantity, cost
   **Explanation**: How these columns combine and what the result will tell us (e.g., "Summing quantity grouped by fruits_name reveals top-selling fruits")
   **Expected Insight**: What we might learn

2. **Name**: Short, clear title
   **Goal**: What insight this analysis would reveal
   **Datasets**: fruits, fruit_quality
   **Columns**: fruits_name, quantity, cost
   **Explanation**: How these columns combine and what the result will tell us
   **Expected Insight**: What we might learn

3. **Name**: Short, clear title
   **Goal**: What insight this analysis would reveal
   **Datasets**: fruits, fruit_quality
   **Columns**: fruits_name, quantity, cost
   **Explanation**: How these columns combine and what the result will tell us
   **Expected Insight**: What we might learn

## Rules
- Start with 1-2 sentences of conversational text acknowledging the user's question
- Then list exactly 3 numbered suggestions in the format shown above
- Put each field on its own line
- Use **bold** around field names for visual highlighting
- Reference only columns and datasets from the context above
- Do NOT generate SQL — just describe the analysis approach
- Keep each suggestion concise (2-3 sentences)
- Make each idea distinct — explore different angles
"""

FOCUS_PROMPT = """You are a data analysis assistant. Current mode: RESEARCH — FOCUSED ANALYSIS.

The user wants to deep-dive on one specific analysis topic. Generate a comprehensive SQL query and provide detailed interpretation.

## Available Datasets
{context}
{enrichment_instruction}

## Instructions
1. Generate ONE SQL query that explores the specific analysis in depth
2. Wrap the SQL in a ```sql code block so the system can extract and execute it
3. After the SQL, provide:
   - What the query analyzes and why it matters
   - Interpretation of expected results
   - 1-2 follow-up questions the user might ask next

## Rules
- Only use columns and tables from the datasets above
- Always include LIMIT 100
- Provide detailed, insightful interpretation
- Suggest natural follow-ups (as questions, not [Action] blocks)

## Chart Decision
After the SQL code block and before your interpretation, output ONE line:
[CHART_DECISION: yes] or [CHART_DECISION: no]

- Choose **yes** if the result has 3+ rows AND multiple columns worth comparing — a bar/line/pie chart would add insight
- Choose **no** if the result is a single number/row, a simple max/min/count/aggregate, or has too few dimensions for a meaningful chart
"""

DEEP_PROMPT = """You are a data analysis assistant. Current mode: RESEARCH — DEEP RESEARCH.

You are conducting a multi-step research investigation. You have access to previous query results and must decide what to explore next.

## Available Datasets
{context}
{enrichment_instruction}

## Previous Iterations
{previous_results}

## Instructions
1. Based on the previous results, decide the NEXT analysis to run
2. Write ONE SQL query wrapped in ```sql code block
3. After the SQL, explain:
   - Why this query is the logical next step
   - What insight it will reveal
4. End your response with one of:
   - **CONTINUE** — There's more to explore. Continue the research.
   - **DONE** — The research is complete. Here's the comprehensive summary.

## Rules
- Each query must build on previous results
- Never repeat a query that was already executed
- Maximum 5 iterations total
- Only use columns and tables from the datasets above
- When DONE, provide a comprehensive summary of all findings

## Chart Decision
After the SQL code block and before your interpretation, output ONE line:
[CHART_DECISION: yes] or [CHART_DECISION: no]

- Choose **[CHART_DECISION: yes]** when the query result has **3+ rows** and **at least 2 numeric columns** that can be compared on a chart — for example:
  - `sales by month` (x=month, y=sales)
  - `quantity by region` (x=region, y=quantity)
  - `price trends over time` (x=date, y=price)
  - Any multi-row result where a bar, line, or pie chart would reveal patterns at a glance

- Choose **[CHART_DECISION: no]** when the result is:
  - A single row or single value (e.g. `total sales = 5000`)
  - A simple count or aggregation with only one meaningful column
  - A result with only 1-2 rows (not enough data for a chart)
  - A list of distinct values with no numeric comparison to make

Be decisive — if the result is rich enough to visualize, say **yes**.
"""

INTERPRET_PROMPT = """You are a data analysis assistant. Interpret the SQL query results below.

## User Question
{question}

## SQL Query Executed
{sql}

## Results
- Row count: {row_count}
- Columns: {columns}
- First {sample_size} rows:
{rows_sample}

## Instructions
Write a concise answer to the user's question based on these results. Include:
1. The direct answer (what the data shows)
2. 1-2 notable observations or patterns
3. One follow-up suggestion (as a question)

## Rules
- Only reference data that appears in the results
- Be specific (use actual numbers/values from the data)
- Keep it concise (3-5 sentences)
"""

# ── Legacy Prompts (kept for backward compatibility) ──

RESEARCH_SYSTEM_PROMPT = """You are a data analysis assistant. Current mode: RESEARCH.

You are AUTHORIZED to discuss, describe, analyze, and reference data from the provided datasets. It is your job to help the user understand this data.

## Available Datasets
{context}
{enrichment_instruction}

## How to respond in RESEARCH mode
Use the context to answer questions and explore the data further. You can:
1. Generate new SQL queries to explore new angles
2. Propose new aims and analysis actions for deeper investigation
3. Explain relationships between datasets and columns
4. Answer follow-up questions about previous analysis results

At the end of your response, include 1-3 brief **proposed analysis actions** (one per line, prefixed with `[Action]`) when relevant — these become clickable pills for the user.

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
- Use markdown (headings, lists, tables, code blocks) for readability
- [Action] proposals must be short (≤10 words), actionable, and specify which dataset they target
"""

SUMMARY_SYSTEM_PROMPT = """You are a data analysis assistant. Current mode: SUMMARY.

You are AUTHORIZED to discuss, describe, analyze, and reference data from the provided datasets. It is your job to help the user understand this data.

## Available Datasets
{context}
{enrichment_instruction}

## How to respond in SUMMARY mode
Recap and summarize findings from the context. Do NOT generate new SQL queries or propose
new analysis actions. Focus on:
1. What was analyzed and what the key findings were
2. Relationships across different analyses
3. Answer questions based on what has already been discovered

## Rules
- Only reference columns and datasets listed in the context above
- Never invent column names, values, or tables
- Use markdown (headings, lists, tables, code blocks) for readability
- If asked to do something that requires a new query, politely explain you're in SUMMARY mode
  and suggest switching to RESEARCH mode
"""


# ── Helpers ──

def build_enrichment_system_prompt(mode: str, dataset_context: str) -> str:
    """Build the mode-specific system prompt with dataset context and enrichment instructions."""
    template = RESEARCH_SYSTEM_PROMPT if mode == "research" else SUMMARY_SYSTEM_PROMPT
    return template.replace("{context}", dataset_context).replace("{enrichment_instruction}", ENRICHMENT_INSTRUCTION)


def extract_sql(text: str) -> str | None:
    """Extract the first SQL code block from text. Returns None if no SQL found."""
    match = re.search(r'```(?:sql)?\s*\n(.*?)\n```', text, re.DOTALL)
    if match:
        sql = match.group(1).strip()
        log_sql("extract_sql", f"found (len={len(sql)})")
        return sql
    log_sql("extract_sql", "not found")
    return None


def extract_sql_fallback(text: str) -> str | None:
    """Fallback: detect inline SELECT ... FROM patterns without code blocks."""
    # Only use fallback when no code block exists
    if re.search(r'```(?:sql)?\s*\n', text, re.DOTALL):
        log_sql("extract_sql_fallback", "skipped (code block present)")
        return None
    match = re.search(
        r'(?:^|\n)(SELECT\s+.+?\s+FROM\s+.+?)(?=\n\n|\n[A-Z]|\Z)',
        text, re.DOTALL | re.IGNORECASE
    )
    if match:
        candidate = match.group(1).strip()
        if len(candidate) > 20:
            log_sql("extract_sql_fallback", f"found (len={len(candidate)})")
            return candidate
    log_sql("extract_sql_fallback", "not found")
    return None


def parse_numbered_suggestions(text: str, known_datasets: list[str] | None = None) -> list[dict]:
    """Parse numbered suggestions from LLM text into structured aim proposals.

    Handles formats like:
    1. **Name**: X  **Goal**: Y  **Datasets**: Z  **Columns**: C  **Explanation**: E  **Expected Insight**: W
    1. Name: X - Goal: Y - Datasets: Z - Columns: C - Explanation: E - Expected Insight: W

    If known_datasets is provided, parsed dataset names are validated against it.
    """
    proposals = []
    known_set = set(known_datasets) if known_datasets else None

    # Try to match structured suggestion items
    items = re.split(r'(?:^|\n)\s*\d+\.\s*', text)
    items = [i.strip() for i in items if i.strip()]

    for item in items:
        if len(item) < 10:
            continue

        name = None
        description = ""
        datasets = []

        # Name
        name_match = re.search(r'\*{0,2}(?:Name|Title)\*{0,2}\s*[:\-–]\s*(.+?)(?:\n|$)', item, re.IGNORECASE)
        if not name_match:
            name_match = re.search(r'(?:^|\n)\s*(.+?)(?:\s*[-–]\s*Goal|\n)', item)
        if name_match:
            name = re.sub(r'\*+', '', name_match.group(1)).strip().replace('<br>', '')

        if not name:
            first_line = item.split('\n')[0].strip()
            if len(first_line) > 5 and len(first_line) < 100:
                name = re.sub(r'\*+', '', first_line).rstrip(':').replace('<br>', '')
            else:
                continue

        # Goal
        goal_match = re.search(r'\*{0,2}Goal\*{0,2}\s*[:\-–]\s*(.+?)(?:\n|$)', item, re.IGNORECASE)
        if goal_match:
            description = goal_match.group(1).strip().rstrip('*').replace('<br>', '')

        # Columns
        cols_match = re.search(r'\*{0,2}Columns?\*{0,2}\s*[:\-–]\s*(.+?)(?:\n|$)', item, re.IGNORECASE)
        if cols_match:
            cols_text = cols_match.group(1).strip().rstrip('*').replace('<br>', '')
            if cols_text:
                description += f"\nColumns: {cols_text}"

        # Explanation
        expl_match = re.search(r'\*{0,2}Explanation\*{0,2}\s*[:\-–]\s*(.+?)(?:\n|$)', item, re.IGNORECASE)
        if expl_match:
            expl_text = expl_match.group(1).strip().rstrip('*').replace('<br>', '')
            if expl_text:
                description += f"\nExplanation: {expl_text}"

        # Expected Insight
        insight_match = re.search(r'\*{0,2}Expected\s*Insight\*{0,2}\s*[:\-–]\s*(.+?)(?:\n|$)', item, re.IGNORECASE)
        if insight_match:
            insight_text = insight_match.group(1).strip().rstrip('*').replace('<br>', '')
            if insight_text:
                description += f"\nExpected Insight: {insight_text}"

        # Datasets (no fallback to Columns/Data since Columns is its own field)
        ds_match = re.search(r'\*{0,2}Datasets?\*{0,2}\s*[:\-–]\s*(.+?)(?:\n|$)', item, re.IGNORECASE)
        if ds_match:
            raw = ds_match.group(1).strip().replace('<br>', '')
            for part in raw.split(','):
                part = part.strip()
                if not part:
                    continue
                base = part.split('(')[0].strip()
                if base:
                    datasets.append(base)
            datasets = list(dict.fromkeys(datasets))

        # Validate datasets against known names if provided
        if known_set:
            datasets = [d for d in datasets if d in known_set]

        # Skip proposals with no valid datasets or garbage aim names
        if not datasets or len(name) < 5:
            continue

        proposals.append({
            "aim": name[:60],
            "description": description[:400],
            "datasets": datasets,
        })

    return proposals[:5]


def route_prompt(question: str) -> str:
    """Build the router prompt with the user's question."""
    return ROUTER_PROMPT.replace("{question}", question)


def deep_prompt(context: str, previous_results: str) -> str:
    """Build the DEEP prompt with context and previous results."""
    return DEEP_PROMPT.replace("{context}", context).replace(
        "{enrichment_instruction}", ENRICHMENT_INSTRUCTION
    ).replace("{previous_results}", previous_results)


def direct_prompt(context: str) -> str:
    """Build the DIRECT prompt with dataset context."""
    return DIRECT_PROMPT.replace("{context}", context).replace(
        "{enrichment_instruction}", ENRICHMENT_INSTRUCTION
    )


def suggest_prompt(context: str) -> str:
    """Build the SUGGEST prompt with dataset context."""
    return SUGGEST_PROMPT.replace("{context}", context).replace(
        "{enrichment_instruction}", ENRICHMENT_INSTRUCTION
    )


def focus_prompt(context: str) -> str:
    """Build the FOCUS prompt with dataset context."""
    return FOCUS_PROMPT.replace("{context}", context).replace(
        "{enrichment_instruction}", ENRICHMENT_INSTRUCTION
    )


# ── LLM Calls ──

async def classify_route(question: str) -> str:
    """Classify user question into a research route."""
    t0 = time.time()
    try:
        settings = get_settings()
        client = get_llm_client()
        response = await client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": "You are a question classifier for a data analysis assistant. Respond with only the category name."},
                {"role": "user", "content": route_prompt(question)},
            ],
            max_tokens=10,
            temperature=0.1,
        )
        route = response.choices[0].message.content.strip().upper()
        if route in ("DIRECT", "SUGGEST", "FOCUS", "DEEP"):
            log_route(question, route, time.time() - t0)
            return route
        logger.warning("Unknown route '%s', defaulting to DIRECT", route)
        log_route(question, "DIRECT(fallback:unknown)", time.time() - t0)
        return "DIRECT"
    except Exception as e:
        logger.exception("Route classification failed")
        log_route(question, f"DIRECT(fallback:error)", time.time() - t0)
        return "DIRECT"


async def generate_llm_response(system_prompt: str, question: str, max_tokens: int | None = None) -> str:
    """Generate a response from the LLM using the given system prompt."""
    t0 = time.time()
    settings = get_settings()
    client = get_llm_client()
    try:
        response = await client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question},
            ],
            max_tokens=max_tokens or settings.max_tokens,
            temperature=settings.temperature,
        )
        content = response.choices[0].message.content or ""
        elapsed = time.time() - t0
        tokens = len(content.split())
        log_llm_call("generate_llm_response", elapsed, tokens)
        log_full_prompt("none", "generate_llm_response", system_prompt[:2000], content[:2000])
        return content
    except Exception as e:
        elapsed = time.time() - t0
        logger.exception("LLM generation failed")
        log_llm_call("generate_llm_response", elapsed, detail=f"ERROR: {str(e)[:100]}")
        raise


async def interpret_results(question: str, sql: str, result: dict) -> str:
    """Interpret SQL query results and answer the user's question."""
    settings = get_settings()
    rows_sample = result.get("rows", [])[:10]
    columns = result.get("columns", [])
    row_count = result.get("row_count", 0)

    prompt = INTERPRET_PROMPT.replace("{question}", question).replace(
        "{sql}", sql
    ).replace("{row_count}", str(row_count)).replace(
        "{columns}", ", ".join(columns)
    ).replace("{sample_size}", str(len(rows_sample))).replace(
        "{rows_sample}", "\n".join(str(r) for r in rows_sample) if rows_sample else "(no data)"
    )
    client = get_llm_client()
    try:
        response = await client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": "You are a data analysis assistant. Interpret SQL results concisely."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=settings.max_tokens,
            temperature=settings.temperature,
        )
        return response.choices[0].message.content or ""
    except Exception as e:
        logger.exception("Result interpretation failed")
        return f"The query returned {row_count} rows. Here are the results: ..."  # fallback


async def summarize_turns(thread_text: str) -> str:
    """Generate a compact summary for a set of turns."""
    settings = get_settings()
    client = get_llm_client()
    try:
        response = await client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": "You are a concise data analysis summarizer. Produce 2-3 sentence summaries."},
                {"role": "user", "content": SUMMARIZE_PROMPT.replace("{thread_text}", thread_text)},
            ],
            max_tokens=settings.max_tokens,
            temperature=settings.temperature,
        )
        return response.choices[0].message.content or ""
    except Exception as e:
        logger.exception("summarize_turns: LLM failed")
        return ""
