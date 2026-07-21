"""LLM client — summary generation and mode-specific prompts."""

import logging
from openai import AsyncOpenAI
from config import get_settings

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


def build_enrichment_system_prompt(mode: str, dataset_context: str) -> str:
    """Build the mode-specific system prompt with dataset context and enrichment instructions."""
    template = RESEARCH_SYSTEM_PROMPT if mode == "research" else SUMMARY_SYSTEM_PROMPT
    return template.replace("{context}", dataset_context).replace("{enrichment_instruction}", ENRICHMENT_INSTRUCTION)


async def summarize_turns(thread_text: str) -> str:
    """Generate a compact summary for a set of turns."""
    settings = get_settings()
    client = AsyncOpenAI(base_url=settings.vllm_base_url, api_key="EMPTY", timeout=settings.llm_request_timeout)
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
