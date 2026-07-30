"""FastAPI routes for the v2 clean-slate manager."""

import re
import uuid
import time
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel

from resolve import resolve_line_lookup, fetch_datasets, save_task_definition
from aims import generate_chat_response, generate_sql, fix_sql, criticize_sql, extract_aims_from_text, extract_analysis_actions, _fallback_chart_configs, _llm_chart_configs, _compute_diagnostics, BASIC_CHART_TYPES, generate_aim, _pivot_data, _crosstab_chart_configs, _aggregate_chart_rows
from llm_client import parse_numbered_suggestions
from logger import log_route, log_llm_call, log_sql, log_aims, log_response, log_full_prompt
from llm_client import summarize_turns, classify_route, extract_sql, extract_sql_fallback, generate_llm_response, interpret_results, direct_prompt, suggest_prompt, focus_prompt, language_instruction
from focus_agent import run_focus_agent, normalize_halfwidth
from sql_executor import validate_sql
from sql_executor import execute_sql
from db.models import GlobalRegistry, ManagerSession
from db.session import AsyncSessionLocal
from config import get_settings
from csv_validator import validate_csv
from column_profile import profile_columns
from sqlite_importer import import_csv_to_sqlite
import sqlite_executor
from user_datasets import (
    draft_column_meanings,
    create_draft_dataset,
    confirm_dataset,
    list_user_datasets,
    delete_user_dataset,
    update_dataset_columns,
    fetch_active_user_datasets,
    llm_fill_missing_meanings,
)
from registry_admin import (
    TableNotFoundError,
    introspect_pg_table,
    create_draft_entry,
    confirm_entry,
    list_entries,
    delete_entry,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v2")
settings = get_settings()

# ── Progress tracking (in-memory, per-session) ──
_progress_store: dict[str, list[dict]] = {}
def set_progress(session_id: str, step: str, status: str, detail: str = ""):
    key = f"progress_{session_id}"
    now = time.time()
    if key not in _progress_store:
        _progress_store[key] = []
    steps = _progress_store[key]
    if status == "running":
        steps.append({"step": step, "status": status, "detail": detail, "ts": now})
    else:
        for s in reversed(steps):
            if s["step"] == step and s["status"] == "running":
                s["status"] = status
                s["detail"] = detail
                s["ts"] = now
                break
    _progress_store[key] = steps[-30:]


# ── Schemas ──

class ResolveRequest(BaseModel):
    line_name: str

class ResolveResponse(BaseModel):
    found: bool
    line_name: str
    canonical: str | None
    source: str | None
    candidates: list[str]
    datasets: list[dict]

class NewResearchRequest(BaseModel):
    user_text: str
    datasets: list[dict]

class NewResearchResponse(BaseModel):
    aim: str
    how_we_will_do_it: str
    datasets_used: list[str]
    joins: str | None

class BucketAddRequest(BaseModel):
    session_id: str
    aim: str
    datasets_used: list[str]
    how_we_will_do_it: str
    joins: str | None

class BucketProceedRequest(BaseModel):
    session_id: str
    bucket_id: str
    aim: str
    line_name: str
    datasets_used: list[str]
    how_we_will_do_it: str

class MessageRequest(BaseModel):
    session_id: str
    message: str
    line_name: str = ""
    attached_aims: list[str] = []
    aim_descriptions: dict[str, str] = {}
    enrichment_mode: str = "research"
    history: list[dict] | None = None
    route_override: str = ""
    language: str = "en"

class AimProposal(BaseModel):
    aim: str
    description: str = ""
    datasets: list[str] = []
    goal: str | None = None
    columns: list[str] | None = None
    insight: str | None = None

class AnalysisAction(BaseModel):
    name: str
    description: str = ""
    datasets: list[str] = []
    goal: str | None = None
    columns: list[str] | None = None
    insight: str | None = None

class SummarizeContextRequest(BaseModel):
    tag: str
    turn_timestamps: list[str]
    user_id: str = ""

class SummarizeContextResponse(BaseModel):
    tag: str
    summary: str
    created_at: str

class ChartConfig(BaseModel):
    chartType: str
    xKey: str
    yKeys: list[str]
    reason: str = ""
    xLabel: str = ""
    yLabel: str = ""
    howToRead: str = ""
    xFormat: str = "auto"
    rows: list[dict] | None = None

class ChartSuggestions(BaseModel):
    advanced: list[ChartConfig] = []
    basic: list[ChartConfig] = []

class QueryResult(BaseModel):
    sql: str
    columns: list[str]
    column_types: list[str] = []
    rows: list[dict]
    row_count: int
    chart_suggestions: ChartSuggestions | None = None

class MessageResponse(BaseModel):
    session_id: str
    turn_index: int = 0
    agent_message: str
    phase: str = "chat"
    status: str = "active"
    ui: dict | None = None
    schema: dict | None = None
    done: bool = True
    description: str | None = None
    benefits: str | None = None
    columns: list[dict] | None = None
    aim_proposals: list[AimProposal] = []
    analysis_actions: list[AnalysisAction] = []
    result_uuid: str | None = None
    query_result: QueryResult | None = None
    route: str = "direct"
    deep_iterations: list = []

class ExecuteQueryRequest(BaseModel):
    session_id: str
    message: str
    line_name: str = ""
    history: list[dict] | None = None

class ExecuteQueryResponse(BaseModel):
    session_id: str
    sql: str
    columns: list[str]
    column_types: list[str] = []
    rows: list[dict]
    row_count: int
    chart_suggestions: ChartSuggestions | None = None

class ColumnProfile(BaseModel):
    datatype: str
    null_pct: float
    distinct_count: int
    is_constant: bool
    zero_pct: float | None = None
    min: str | None = None
    max: str | None = None
    common_samples: list[str] = []

class UploadedFileReport(BaseModel):
    dataset_id: int
    dataset_name: str
    table_name: str
    filename: str
    columns: list[dict]
    profiling: dict[str, ColumnProfile] = {}
    row_count: int
    warnings: list[str] = []

class UploadFailure(BaseModel):
    filename: str
    errors: list[str]

class UploadResponse(BaseModel):
    status: str
    files: list[UploadedFileReport] = []
    failures: list[UploadFailure] = []

class ConfirmDatasetRequest(BaseModel):
    user_id: str = ""
    columns: list[dict]
    description: str = ""

class LlmFillRequest(BaseModel):
    user_id: str = ""
    columns: list[str]
    language: str = "en"

class LoginRequest(BaseModel):
    user_id: str

class LoginResponse(BaseModel):
    user_id: str
    role: str

class IntrospectRequest(BaseModel):
    table_name: str

class CreateRegistryEntryRequest(BaseModel):
    maintained_by: str
    line_name: str
    dataset_name: str
    table_name: str
    description: str = ""
    column_definitions: list[dict]
    role: str | None = None
    join_hints: dict | list | None = None
    suggested_aims: dict | list | None = None
    synonyms: list[str] | None = None

class ConfirmRegistryEntryRequest(BaseModel):
    user_id: str = ""
    columns: list[dict]
    description: str = ""

# ── Helpers ──

def _column_meanings_from_datasets(datasets_data: list[dict] | None) -> dict[str, str]:
    """Flatten column_definitions across all attached datasets into name -> meaning,
    so the chart-selection prompt knows what a column actually represents
    (not just its SQL name/type)."""
    meanings: dict[str, str] = {}
    for ds in datasets_data or []:
        for c in ds.get("column_definitions") or []:
            name = c.get("name")
            meaning = c.get("meaning")
            if name and meaning and name not in meanings:
                meanings[name] = meaning
    return meanings


async def _build_chart_suggestions(result: dict, datasets_data: list[dict] | None = None) -> ChartSuggestions | None:
    """Build chart suggestions from SQL result.

    Primary path: one LLM call grounded in the chart types' actual meaning,
    each column's real business meaning (from the dataset registry), AND
    precomputed per-column data diagnostics (distinct count, nulls,
    zero/dominant-value ratios, hierarchy checks) — so chart choice reflects
    whether the data structurally AND semantically fits, not just whether
    the column types match.
    Falls back to the deterministic rule-based generator (which applies the
    same diagnostic guards) if the LLM call fails or returns nothing usable.

    Always merges LLM + fallback + crosstab configs so users see full variety.
    """
    columns = result.get("columns")
    rows = result.get("rows")
    if not columns or not rows:
        return None
    column_types = result.get("column_types", [])

    diagnostics = _compute_diagnostics(columns, column_types, rows)
    column_meanings = _column_meanings_from_datasets(datasets_data)
    proposals = await _llm_chart_configs(columns, column_types, rows, diagnostics, column_meanings)
    raw = _fallback_chart_configs(columns, column_types, rows)
    crosstab = _crosstab_chart_configs(columns, column_types, rows)

    def key(c: dict) -> tuple:
        return (c["chartType"], c["xKey"], str(c.get("yKeys", [])))

    # Basic charts: deduplicate by chartType only (keep one per type, prefer LLM)
    seen_basic: set[str] = set()
    basic_items: list[dict] = []
    for c in (proposals or []):
        ct = c["chartType"]
        if ct in BASIC_CHART_TYPES and ct not in seen_basic:
            seen_basic.add(ct)
            basic_items.append(c)
    for c in (raw.get("basic", [])):
        ct = c["chartType"]
        if ct in BASIC_CHART_TYPES and ct not in seen_basic:
            seen_basic.add(ct)
            basic_items.append(c)

    # Advanced charts: dedup by full key (chartType + xKey + yKeys), LLM first
    merged_adv: dict[tuple, dict] = {}
    for c in (proposals or []):
        if c["chartType"] not in BASIC_CHART_TYPES:
            merged_adv[key(c)] = c
    for c in (raw.get("advanced", [])):
        k = key(c)
        if k not in merged_adv:
            merged_adv[k] = c

    # Crosstab configs always added to advanced
    crosstab_keys = set()
    for c in crosstab:
        k = key(c)
        merged_adv[k] = c
        crosstab_keys.add(k)

    advanced = list(merged_adv.values())
    basic = basic_items

    numeric_cols = [c for c, t in zip(columns, column_types)
                    if t in ("integer", "float", "decimal", "numeric", "bigint", "smallint")]
    for c in advanced + basic:
        if c.get("rows"):
            continue
        agg_rows = _aggregate_chart_rows(c["chartType"], c["xKey"], c["yKeys"], rows, numeric_cols)
        if agg_rows:
            c["rows"] = agg_rows

    return ChartSuggestions(
        advanced=[ChartConfig(**c) for c in advanced],
        basic=[ChartConfig(**c) for c in basic],
    )

# ── Enrichment ──

def estimate_tokens(text: str) -> int:
    """Rough token estimation: ~4 chars per token."""
    return len(text) // 4 + 1


def build_enrichment_block(
    state: dict,
    attached_aims: list[str],
    attached_datasets: list[str],
    mode: str,
    max_tokens: int = 4000,
) -> str:
    """Build an enrichment block replacing flat history with tagged summaries + relevant turns."""
    blocks: list[str] = []
    seen_timestamps: set[str] = set()
    total_tokens = 0

    if mode == "research":
        if not attached_aims and not attached_datasets:
            return ""
        tags = [f"aim:{a}" for a in attached_aims] + [f"dataset:{d}" for d in attached_datasets]
    elif mode == "summary":
        tags = list(state.get("context_summaries", {}).keys())
    else:
        return ""

    summaries = state.get("context_summaries", {})
    turns = state.get("turns", [])
    chat_results = state.get("chat_query_results", {})

    for tag in tags:
        tag_summaries = summaries.get(tag, [])
        covered_ts: set[str] = set()
        for s in tag_summaries:
            covered_ts.update(s["turn_timestamps"])
            if all(ts in seen_timestamps for ts in s["turn_timestamps"]):
                continue
            text = f"[Summary: {tag}] {s['summary']}"
            tokens = estimate_tokens(text)
            if total_tokens + tokens > max_tokens:
                break
            blocks.append(text)
            total_tokens += tokens
            seen_timestamps.update(s["turn_timestamps"])

        tag_name = tag.split(":", 1)[1]
        relevant_turns = [
            t for t in turns
            if tag_name in (t.get("aims") or []) or tag_name in (t.get("datasets") or [])
        ]
        uncovered = [t for t in relevant_turns if t.get("created_at") not in covered_ts and t.get("timestamp") not in covered_ts]

        for t in uncovered[-5:]:
            ts = t.get("created_at") or t.get("timestamp")
            if ts in seen_timestamps:
                continue
            result_text = ""
            result_uuid = t.get("result_uuid")
            if result_uuid:
                r = chat_results.get(result_uuid, {})
                if r:
                    sql = r.get("sql", "")
                    sql_display = sql[:80] + " ... [truncated]" if len(sql) > 80 else sql
                    result_text = f" | SQL: {sql_display} | Rows: {r.get('row_count', 0)}"
            else:
                ts_fallback = t.get("created_at") or t.get("timestamp") or ""
                r = chat_results.get(ts_fallback, {})
                if r:
                    sql = r.get("sql", "")
                    sql_display = sql[:80] + " ... [truncated]" if len(sql) > 80 else sql
                    result_text = f" | SQL: {sql_display} | Rows: {r.get('row_count', 0)}"

            user_text = (t.get("user") or "")[:80]
            agent_text = (t.get("agent") or "")[:80]
            text = f"[Turn] User: {user_text} | Agent: {agent_text}{result_text}"
            tokens = estimate_tokens(text)
            if total_tokens + tokens > max_tokens:
                break
            blocks.append(text)
            total_tokens += tokens
            if ts:
                seen_timestamps.add(ts)

    return "\n".join(blocks)


def build_conversation_history(turns: list[dict], max_turns: int = 5) -> str:
    """Build a conversation history block from stored turns."""
    history_blocks = []
    for t in turns[-max_turns:]:
        user_text = (t.get("user") or "")[:200]
        agent_text = (t.get("agent") or "")[:200]
        history_blocks.append(f"User: {user_text}\nAssistant: {agent_text}")
    if history_blocks:
        return "\n\n".join(history_blocks)
    return ""


async def _get_session_owned(session_id: str, user_id: str | None) -> ManagerSession:
    """Fetch a session by ID and verify the requesting user owns it.
    Returns the session or raises 404/403."""
    if not user_id:
        raise HTTPException(status_code=403, detail="user_id is required for this operation")
    async with AsyncSessionLocal() as db:
        from sqlalchemy import select
        row = (await db.execute(
            select(ManagerSession).where(ManagerSession.session_id == session_id)
        )).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Session not found")
    if row.user_id != user_id:
        raise HTTPException(status_code=403, detail="You do not own this session")
    return row


# ── Routes ──

@router.post("/resolve-line", response_model=ResolveResponse)
async def resolve_line(req: ResolveRequest):
    """Fuzzy-match a line name against global_registry."""
    raw = req.line_name.strip()
    if not raw:
        raise HTTPException(status_code=400, detail="line_name is required")

    match = await resolve_line_lookup(raw)
    if match is None:
        return ResolveResponse(
            found=False,
            line_name=raw,
            canonical=None,
            source=None,
            candidates=[],
            datasets=[],
        )

    if match.source == "ambiguous":
        return ResolveResponse(
            found=False,
            line_name=raw,
            canonical=None,
            source="ambiguous",
            candidates=match.candidates,
            datasets=[],
        )

    datasets = await fetch_datasets(match.canonical)
    return ResolveResponse(
        found=True,
        line_name=raw,
        canonical=match.canonical,
        source=match.source,
        candidates=[],
        datasets=datasets,
    )

@router.post("/aim/new-research", response_model=NewResearchResponse)
async def new_research(req: NewResearchRequest):
    """LLM generates a structured aim from user text + selected datasets."""
    if not req.user_text.strip():
        raise HTTPException(status_code=400, detail="user_text is required")
    if not req.datasets:
        raise HTTPException(status_code=400, detail="at least one dataset is required")

    result = await generate_aim(req.user_text, req.datasets)
    return NewResearchResponse(
        aim=result.get("aim", ""),
        how_we_will_do_it=result.get("how_we_will_do_it", ""),
        datasets_used=result.get("datasets_used", [d["dataset_name"] for d in req.datasets]),
        joins=result.get("joins"),
    )

@router.post("/bucket/proceed")
async def bucket_proceed(req: BucketProceedRequest):
    """Save an aim to task_registry and trigger execution."""
    async with AsyncSessionLocal() as db:
        from sqlalchemy import select
        session = (await db.execute(
            select(ManagerSession).where(ManagerSession.session_id == req.session_id)
        )).scalar_one_or_none()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        uid = session.user_id
    task_def = {
        "aims": [req.aim],
        "how_we_will_do_it": req.how_we_will_do_it,
        "datasets_used": req.datasets_used,
        "source": "v2_workspace",
    }
    try:
        version = await save_task_definition(req.line_name, uid, task_def)
        return {"status": "proceeded", "line_name": req.line_name, "version": version, "task_def": task_def}
    except Exception as e:
        logger.exception("bucket_proceed: failed")
        raise HTTPException(status_code=500, detail=str(e)[:200])

@router.post("/execute-query", response_model=ExecuteQueryResponse)
async def execute_query(req: ExecuteQueryRequest):
    """Generate and execute SQL from a user query, returning results."""
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="message is required")

    dataset_names = [d.strip() for d in req.line_name.split(",") if d.strip()]
    if not dataset_names:
        raise HTTPException(status_code=400, detail="At least one dataset is required")

    datasets_data = []
    async with AsyncSessionLocal() as db:
        from sqlalchemy import select
        result = await db.execute(
            select(GlobalRegistry).where(
                GlobalRegistry.dataset_name.in_(dataset_names),
                GlobalRegistry.status == "active",
            )
        )
        for reg in result.scalars().all():
            datasets_data.append({
                "dataset_name": reg.dataset_name,
                "table": reg.source_config.get("table") if reg.source_config else reg.dataset_name,
                "description": reg.description,
                "column_definitions": reg.column_definitions,
                "join_hints": reg.join_hints,
            })

    if not datasets_data:
        raise HTTPException(status_code=404, detail="No datasets found for the given names")

    sql = await generate_sql(
        message=req.message,
        datasets_data=datasets_data,
        history=req.history,
    )

    # Two-agent loop: writer → critic → fix (if needed) → critic → execute
    for attempt in range(3):
        # Critic reviews SQL before execution
        critique = await criticize_sql(
            sql=sql,
            message=req.message,
            datasets_data=datasets_data,
        )

        if critique.get("pass"):
            # Critic approved — execute
            try:
                result = await execute_sql(sql)
            except Exception as e:
                # Runtime failure (unlikely after critic) — feed back to fix
                logger.warning("SQL passed critic but failed at runtime: %s", str(e)[:200])
                if attempt < 2:
                    sql = await fix_sql(
                        bad_sql=sql,
                        error=str(e)[:300],
                        message=req.message,
                        datasets_data=datasets_data,
                        suggestions=critique.get("suggestions", ""),
                    )
                    continue
                break
            # Chart suggestions are best-effort — never block the response
            try:
                chart_suggestions = await _build_chart_suggestions(result, datasets_data)
            except Exception:
                chart_suggestions = None
            return ExecuteQueryResponse(
                session_id=req.session_id,
                **result,
                chart_suggestions=chart_suggestions,
            )

        # Critic rejected — feed issues to fix agent
        issues = critique.get("issues", ["Unknown issue"])
        suggestions = critique.get("suggestions", "")
        logger.warning("SQL attempt %d critic issues: %s", attempt + 1, issues)

        if attempt < 2:
            sql = await fix_sql(
                bad_sql=sql,
                error="; ".join(issues),
                message=req.message,
                datasets_data=datasets_data,
                suggestions=suggestions,
            )
            continue
        break

    # Last resort: try executing whatever SQL we have
    try:
        result = await execute_sql(sql)
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Failed to generate a working query. Try rephrasing your request.",
        )
    try:
        chart_suggestions = await _build_chart_suggestions(result, datasets_data)
    except Exception:
        chart_suggestions = None
    return ExecuteQueryResponse(session_id=req.session_id, **result, chart_suggestions=chart_suggestions)


class CreateSessionRequest(BaseModel):
    title: str | None = None
    user_id: str = ""

class UpdateSessionRequest(BaseModel):
    title: str | None = None
    state: dict | None = None
    user_id: str = ""

@router.post("/sessions")
async def create_session(body: CreateSessionRequest = None):
    """Create a new session."""
    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    title = body.title if body and body.title else f"Session {session_id[:8]}"
    uid = (body.user_id or settings.default_user_id) if body else settings.default_user_id
    async with AsyncSessionLocal() as db:
        row = ManagerSession(
            session_id=session_id,
            user_id=uid,
            phase="lines",
            status="active",
            title=title,
            state_json={},
            created_at=now,
            updated_at=now,
        )
        db.add(row)
        await db.commit()
    return {"session_id": session_id, "title": row.title}

@router.patch("/sessions/{session_id}")
async def update_session(session_id: str, body: UpdateSessionRequest):
    """Update session metadata (title, etc.)."""
    row = await _get_session_owned(session_id, body.user_id or None)
    async with AsyncSessionLocal() as db:
        from sqlalchemy import select
        row = (await db.execute(
            select(ManagerSession).where(ManagerSession.session_id == session_id)
        )).scalar_one_or_none()
        if body.title is not None:
            row.title = body.title
        if body.state is not None:
            state = dict(row.state_json or {})
            state.update(body.state)
            row.state_json = state
        row.updated_at = datetime.now(timezone.utc)
        await db.commit()
    return {"session_id": session_id, "title": row.title}

@router.get("/sessions")
async def list_sessions(user_id: str = ""):
    """List sessions, optionally filtered by user_id."""
    async with AsyncSessionLocal() as db:
        from sqlalchemy import select
        stmt = select(ManagerSession)
        if user_id:
            stmt = stmt.where(ManagerSession.user_id == user_id)
        stmt = stmt.order_by(ManagerSession.updated_at.desc()).limit(50)
        result = await db.execute(stmt)
        rows = result.scalars().all()
    return [
        {
            "session_id": r.session_id,
            "title": r.title,
            "phase": r.phase,
            "status": r.status,
            "created_at": str(r.created_at) if r.created_at else None,
        }
        for r in rows
    ]

@router.get("/sessions/{session_id}")
async def get_session(session_id: str, user_id: str = ""):
    """Get session details."""
    row = await _get_session_owned(session_id, user_id or None)
    state = row.state_json or {}
    return {
        "session_id": row.session_id,
        "title": row.title,
        "phase": row.phase,
        "status": row.status,
        "state": state,
        "turns": state.get("turns", []),
    }

@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, user_id: str = ""):
    """Delete a session and everything tied to it (turns, query results, chart state
    all live inside state_json, so deleting the row deletes all of it)."""
    await _get_session_owned(session_id, user_id or None)
    async with AsyncSessionLocal() as db:
        from sqlalchemy import delete as sa_delete
        await db.execute(sa_delete(ManagerSession).where(ManagerSession.session_id == session_id))
        await db.commit()
    return {"status": "deleted", "session_id": session_id}

@router.get("/sessions/{session_id}/progress")
async def get_session_progress(session_id: str):
    """Return progress steps for the latest message processing on this session."""
    key = f"progress_{session_id}"
    return {"steps": _progress_store.get(key, [])}

@router.get("/datasets")
async def list_datasets():
    """List all datasets from global_registry."""
    async with AsyncSessionLocal() as db:
        from sqlalchemy import select
        result = await db.execute(select(GlobalRegistry).where(GlobalRegistry.status == "active"))
        rows = result.scalars().all()
    return [
        {
            "line_name": r.line_name,
            "dataset_name": r.dataset_name,
            "description": r.description,
            "table": r.source_config.get("table") if r.source_config else None,
            "column_definitions": r.column_definitions,
            "role": r.role,
            "join_hints": r.join_hints,
            "suggested_aims": r.suggested_aims,
            "synonyms": r.synonyms,
        }
        for r in rows
    ]

@router.get("/user-datasets")
async def get_user_datasets(user_id: str = ""):
    """List the current user's personal (uploaded CSV) datasets — separate from global_registry."""
    uid = user_id or settings.default_user_id
    return {"datasets": await list_user_datasets(uid)}

@router.post("/upload", response_model=UploadResponse)
async def upload_csv(files: list[UploadFile] = File(...), user_id: str = Form(default="")):
    """Validate + import one or more CSVs into the user's personal SQLite file.
    Each file lands as a 'draft' dataset — not usable until confirmed via /upload/{id}/confirm."""
    uid = user_id or settings.default_user_id
    reports: list[UploadedFileReport] = []
    failures: list[UploadFailure] = []

    for f in files:
        raw = await f.read()
        result = validate_csv(
            raw, f.filename or "upload.csv",
            max_size_mb=settings.max_upload_size_mb,
            max_bad_row_pct=settings.max_bad_row_pct,
        )
        if result.status == "fail":
            failures.append(UploadFailure(filename=f.filename or "upload.csv", errors=result.errors))
            continue

        try:
            imported = import_csv_to_sqlite(uid, result.table_name, result.columns, result.column_types, result.rows)
        except Exception as e:
            logger.exception("upload_csv: sqlite import failed for %s", f.filename)
            failures.append(UploadFailure(filename=f.filename or "upload.csv", errors=[f"Import failed: {str(e)[:200]}"]))
            continue

        # Profile columns for initial analysis display
        profiling = profile_columns(result.columns, result.rows)

        # Start with blank meanings — no auto LLM draft
        column_defs = [
            {"name": c, "original_name": r, "datatype": t, "meaning": ""}
            for c, r, t in zip(result.columns, result.raw_columns, result.column_types)
        ]

        dataset_id = await create_draft_dataset(
            user_id=uid,
            dataset_name=result.table_name,
            table_name=result.table_name,
            sqlite_path=imported["db_path"],
            original_filename=f.filename or "upload.csv",
            column_definitions=column_defs,
            column_profiling=profiling,
            row_count=result.row_count,
        )
        reports.append(UploadedFileReport(
            dataset_id=dataset_id,
            dataset_name=result.table_name,
            table_name=result.table_name,
            filename=f.filename or "upload.csv",
            columns=column_defs,
            profiling=profiling,
            row_count=result.row_count,
            warnings=result.warnings,
        ))

    if reports and not failures:
        status = "ok"
    elif reports and failures:
        status = "partial"
    else:
        status = "fail"
    return UploadResponse(status=status, files=reports, failures=failures)

@router.post("/upload/{dataset_id}/confirm")
async def confirm_upload(dataset_id: int, req: ConfirmDatasetRequest):
    """User clicked 'All set' in the column-clarification view — lock the edited meanings in."""
    uid = req.user_id or settings.default_user_id
    try:
        return await confirm_dataset(uid, dataset_id, req.columns, req.description)
    except ValueError:
        raise HTTPException(status_code=404, detail="Dataset not found")

@router.post("/upload/{dataset_id}/llm-fill")
async def llm_fill_upload(dataset_id: int, req: LlmFillRequest):
    """User clicked 'LLM fill' — generate meanings for empty columns via LLM."""
    uid = req.user_id or settings.default_user_id
    try:
        return await llm_fill_missing_meanings(uid, dataset_id, req.columns, language=req.language)
    except ValueError:
        raise HTTPException(status_code=404, detail="Dataset not found")

@router.patch("/user-datasets/{dataset_id}/columns")
async def patch_dataset_columns(dataset_id: int, req: ConfirmDatasetRequest):
    """Update column definitions and description for an existing (active) personal dataset."""
    uid = req.user_id or settings.default_user_id
    try:
        return await update_dataset_columns(uid, dataset_id, req.columns, req.description)
    except ValueError:
        raise HTTPException(status_code=404, detail="Dataset not found")

@router.delete("/user-datasets/{dataset_id}")
async def remove_user_dataset(dataset_id: int, user_id: str = ""):
    uid = user_id or settings.default_user_id
    try:
        await delete_user_dataset(uid, dataset_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return {"status": "deleted", "id": dataset_id}

@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest):
    """Stateless ID-only allowlist check — no passwords. Decides which top-level view the
    frontend renders (IoT registration page vs the normal dashboard)."""
    role = "iot" if req.user_id.strip().lower() in settings.get_iot_user_ids() else "normal"
    return LoginResponse(user_id=req.user_id.strip(), role=role)

@router.post("/registry-admin/introspect")
async def registry_introspect(req: IntrospectRequest):
    """Look up an existing Postgres table's columns + a sample, and draft column meanings —
    nothing is saved yet, same preview-before-commit shape as CSV upload."""
    try:
        columns, sample_rows = await introspect_pg_table(req.table_name)
    except TableNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    col_names = [c["name"] for c in columns]
    drafted = await draft_column_meanings(req.table_name, col_names, sample_rows)
    meaning_by_name = {d["name"]: d["meaning"] for d in drafted}
    for c in columns:
        c["meaning"] = meaning_by_name.get(c["name"], "")
    return {"table_name": req.table_name, "columns": columns, "sample_rows": sample_rows[:5]}

@router.post("/registry-admin/entries")
async def registry_create_entry(req: CreateRegistryEntryRequest):
    entry_id = await create_draft_entry(
        maintained_by=req.maintained_by,
        line_name=req.line_name,
        dataset_name=req.dataset_name,
        table_name=req.table_name,
        description=req.description,
        column_definitions=req.column_definitions,
        role=req.role,
        join_hints=req.join_hints,
        suggested_aims=req.suggested_aims,
        synonyms=req.synonyms,
    )
    return {"id": entry_id, "status": "draft"}

@router.post("/registry-admin/entries/{entry_id}/confirm")
async def registry_confirm_entry(entry_id: int, req: ConfirmRegistryEntryRequest):
    try:
        return await confirm_entry(entry_id, req.columns, req.description, user_id=req.user_id or None)
    except ValueError:
        raise HTTPException(status_code=404, detail="Entry not found")

@router.get("/registry-admin/entries")
async def registry_list_entries(maintained_by: str = ""):
    return {"entries": await list_entries(maintained_by or None)}

@router.delete("/registry-admin/entries/{entry_id}")
async def registry_delete_entry(entry_id: int, user_id: str = ""):
    try:
        await delete_entry(entry_id, user_id=user_id or None)
    except ValueError:
        raise HTTPException(status_code=404, detail="Entry not found")
    return {"status": "deleted", "id": entry_id}

# ── Route Handlers ──

async def _fetch_sample_rows(ds: dict, limit: int = 5) -> list[dict]:
    """Fetch up to `limit` sample rows from a dataset for context previews."""
    table = ds.get("table") or ds.get("dataset_name", "")
    if not table:
        return []
    try:
        if ds.get("backend") == "sqlite":
            db_path = ds.get("sqlite_path")
            if not db_path:
                return []
            result = await sqlite_executor.execute_sql(db_path, f'SELECT * FROM "{table}" LIMIT {limit}')
            return result.get("rows", [])
        else:
            result = await execute_sql(f'SELECT * FROM "{table}" LIMIT {limit}')
            return result.get("rows", [])
    except Exception:
        return []


def _format_sample_values(rows: list[dict], col_name: str, max_samples: int = 3) -> str:
    """Extract up to `max_samples` distinct non-null values for a column from sample rows."""
    seen = set()
    values = []
    for row in rows:
        val = row.get(col_name)
        if val is not None and str(val).strip() and str(val) not in seen:
            seen.add(str(val))
            values.append(str(val))
            if len(values) >= max_samples:
                break
    if not values:
        return ""
    return f" e.g. {', '.join(repr(v) for v in values)}"


async def _build_context(
    dataset_names: list[str],
    datasets_data: list[dict],
    attached_aims: list[str],
    aim_descriptions: dict[str, str] | None = None,
    include_samples: bool = True,
) -> str:
    """Build a context string describing datasets and attached aims with column details
    and optionally sample values. include_samples should be False for the FOCUS route
    so the LLM actually queries data instead of answering from sample values."""
    parts = [f"Available datasets: {', '.join(dataset_names) if dataset_names else 'None'}"]
    if attached_aims:
        aim_descriptions = aim_descriptions or {}
        aim_lines = [
            f"{aim} — {aim_descriptions[aim]}" if aim_descriptions.get(aim) else aim
            for aim in attached_aims
        ]
        parts.append(f"Active research aims:\n" + "\n".join(f"- {line}" for line in aim_lines))
    for ds in datasets_data:
        cols = ds.get("column_definitions", [])
        table = ds.get("table") or ds.get("dataset_name", "?")
        sample_rows = await _fetch_sample_rows(ds) if include_samples else None
        if sample_rows:
            sample_rows = [
                {k: normalize_halfwidth(v) if isinstance(v, str) else v for k, v in row.items()}
                for row in sample_rows
            ]
        profiling = ds.get("column_profiling", {})
        col_lines = []
        for c in cols:
            name_display = c.get('original_name', c.get('name', '?'))
            dtype = c.get('datatype', '?')
            meaning = c.get('meaning', '')
            sql_name = c.get('name', '')
            samples = _format_sample_values(sample_rows, sql_name) if include_samples and sql_name and sample_rows else ""
            col_info = f"{name_display} ({dtype})"
            if meaning:
                col_info += f" — {meaning}"
            if samples:
                col_info += samples
            # Append profiling hints
            p = profiling.get(sql_name, {})
            hints = []
            if p.get("is_constant"):
                hints.append("constant value")
            zero_pct = p.get("zero_pct")
            if zero_pct is not None and zero_pct > 0:
                hints.append(f"{zero_pct}% zeros")
            if p.get("null_pct", 0) > 5:
                hints.append(f"{p['null_pct']}% empty")
            if p.get("min") is not None and p.get("max") is not None:
                hints.append(f"range {p['min']}–{p['max']}")
            if hints:
                col_info += f" [{', '.join(hints)}]"
            col_lines.append(col_info)
        col_str = "; ".join(col_lines)
        parts.append(f"Dataset '{ds.get('dataset_name','?')}' (SQL table name: `{table}`): {col_str}")
        if ds.get("description"):
            parts.append(f"  Description: {ds['description']}")
        if ds.get("join_hints"):
            parts.append(f"  Join hints: {ds['join_hints']}")
    return "\n".join(parts)


async def _handle_direct(
    session_id: str,
    message: str,
    dataset_names: list[str],
    datasets_data: list[dict],
    attached_aims: list[str],
    enrichment_block: str = "",
    aim_descriptions: dict[str, str] | None = None,
    session_state: dict | None = None,
    language: str = "en",
):
    """DIRECT route: LLM generates SQL → we validate and execute → LLM interprets results."""
    set_progress(session_id, "building_context", "running", "Analyzing dataset schema...")
    context = await _build_context(dataset_names, datasets_data, attached_aims, aim_descriptions)
    set_progress(session_id, "building_context", "done", f"{len(datasets_data)} datasets analyzed")

    set_progress(session_id, "generating_sql", "running", "Generating SQL query...")
    system_prompt = direct_prompt(context=context, language=language)
    if enrichment_block:
        system_prompt += f"\n\n## Previous Context\n{enrichment_block}"
    raw = await generate_llm_response(
        system_prompt=system_prompt,
        question=message,
    )
    sql = extract_sql(raw)
    if not sql:
        sql = extract_sql_fallback(raw)

    # Retry with a stricter SQL-only prompt if no SQL generated
    if not sql:
        set_progress(session_id, "generating_sql", "running", "Retrying SQL generation...")
        log_sql("retry", "No SQL in first response, retrying with stricter prompt")
        sql_only_prompt = (
            f"You are a SQL generator. Given the user question and available datasets below, "
            f"output ONLY a single SQL query wrapped in ```sql code blocks. "
            f"Do NOT output any explanation, suggestions, or numbered lists. "
            f"Just the SQL. Nothing else.\n\n"
            f"Available datasets:\n{context}\n\n"
            f"User question: {message}"
        )
        raw2 = await generate_llm_response(
            system_prompt=sql_only_prompt,
            question=message,
            max_tokens=1024,
        )
        sql = extract_sql(raw2)
        if not sql:
            sql = extract_sql_fallback(raw2)
        if sql:
            raw = raw2  # Use the retry response for interpretation

    if not sql:
        set_progress(session_id, "generating_sql", "done", "No SQL — switching to suggestions")
        known_columns = {
            c.get("name", "")
            for ds in datasets_data
            for c in ds.get("column_definitions", [])
            if c.get("name")
        }
        proposals = parse_numbered_suggestions(raw, known_datasets=dataset_names, known_columns=known_columns)
        if not proposals:
            proposals = _fallback_aim_suggestions(datasets_data)
        return {
            "agent_message": raw,
            "result_uuid": None,
            "query_result": None,
            "aim_proposals": proposals,
        }
    set_progress(session_id, "generating_sql", "done", "SQL generated")

    set_progress(session_id, "validating_sql", "running", "Validating SQL safety...")
    try:
        sql = validate_sql(sql)
    except ValueError as e:
        set_progress(session_id, "validating_sql", "done", "Validation failed")
        error_result = {
            "sql": sql,
            "columns": [],
            "column_types": [],
            "rows": [],
            "row_count": 0,
        }
        return {
            "agent_message": f"I generated a SQL query but it couldn't be validated:\n\n```sql\n{sql}\n```\n\n**Validation error:** {str(e)}\n\nCould you clarify what you're looking for?",
            "result_uuid": None,
            "query_result": error_result,
        }
    set_progress(session_id, "validating_sql", "done", "SQL validated")

    set_progress(session_id, "executing_query", "running", "Running query...")
    try:
        result = await execute_sql(sql)
    except Exception as e:
        set_progress(session_id, "executing_query", "done", "Query failed")
        error_msg = str(e)[:300]
        error_result = {
            "sql": sql,
            "columns": [],
            "column_types": [],
            "rows": [],
            "row_count": 0,
        }
        interpretation = await generate_llm_response(
            system_prompt=f"You are a data analyst assistant. The SQL query failed with error: {error_msg}. Explain the error briefly and suggest how to fix it." + language_instruction(language),
            question=f"The query was:\n```sql\n{sql}\n```",
        )
        return {
            "agent_message": interpretation,
            "result_uuid": None,
            "query_result": error_result,
        }
    set_progress(session_id, "executing_query", "done", f"{result.get('row_count', 0)} rows returned")

    set_progress(session_id, "building_charts", "running", "Building chart suggestions...")
    chart_suggestions = await _build_chart_suggestions(result, datasets_data)
    result_with_charts = {**result, "chart_suggestions": chart_suggestions}
    set_progress(session_id, "building_charts", "done", "Charts ready")

    set_progress(session_id, "interpreting_results", "running", "Interpreting results...")
    interpretation = await interpret_results(
        question=message,
        sql=result.get("sql", ""),
        result=result,
        language=language,
    )
    set_progress(session_id, "interpreting_results", "done", "Interpretation ready")

    result_uuid = str(uuid.uuid4())
    return {
        "agent_message": interpretation,
        "result_uuid": result_uuid,
        "query_result": result_with_charts,
    }


def _fallback_aim_suggestions(datasets_data: list[dict]) -> list[dict]:
    """Generate simple rule-based analysis suggestions from dataset column definitions.
    Used when the LLM fails to produce valid suggestions."""
    proposals = []
    NUMERIC_TYPES = {"integer", "float", "number", "real", "numeric", "double"}
    CAT_TYPES = {"text", "varchar", "char", "string", "category"}
    DATE_TYPES = {"date", "timestamp", "datetime", "time"}

    def col_label(name: str) -> str:
        return name.replace("_", " ").title() if name else name

    for ds in datasets_data:
        cols = ds.get("column_definitions", [])
        dataset_name = ds.get("dataset_name", "?")
        numeric = [c["name"] for c in cols if c.get("datatype", "").lower() in NUMERIC_TYPES]
        cat = [c["name"] for c in cols if c.get("datatype", "").lower() in CAT_TYPES]
        date = [c["name"] for c in cols if c.get("datatype", "").lower() in DATE_TYPES]

        local = []

        # Pattern 1: Numeric broken down by categorical
        if numeric and cat:
            n = numeric[0]
            c = cat[0]
            local.append({
                "aim": f"Analysis of {col_label(n)} by {col_label(c)}",
                "description": (
                    f"**Goal**: Understand how {col_label(n)} varies across {col_label(c)}\n"
                    f"**Columns**: {n}, {c}\n"
                    f"**Explanation**: Group {col_label(n)} by {col_label(c)} to find top performers and outliers."
                ),
                "datasets": [dataset_name],
                "goal": f"Understand how {col_label(n)} varies across {col_label(c)}",
                "columns": [n, c],
                "insight": f"Top {col_label(c)} categories ranked by {col_label(n)}",
            })

        # Pattern 2: Numeric trend over date
        if numeric and date:
            n = numeric[0]
            d = date[0]
            local.append({
                "aim": f"Trend of {col_label(n)} Over Time",
                "description": (
                    f"**Goal**: Analyze {col_label(n)} trends over {col_label(d)}\n"
                    f"**Columns**: {d}, {n}\n"
                    f"**Explanation**: Plot {col_label(n)} across {col_label(d)} to identify trends, peaks, and seasonal patterns."
                ),
                "datasets": [dataset_name],
                "goal": f"Analyze {col_label(n)} trends over {col_label(d)}",
                "columns": [d, n],
                "insight": f"Trend direction and notable changes in {col_label(n)} over time",
            })

        # Pattern 3: Two categorical + numeric (cross-analysis)
        if numeric and len(cat) >= 2:
            n = numeric[0]
            c1, c2 = cat[0], cat[1]
            local.append({
                "aim": f"Cross-analysis: {col_label(n)} by {col_label(c1)} and {col_label(c2)}",
                "description": (
                    f"**Goal**: Compare {col_label(n)} across both {col_label(c1)} and {col_label(c2)}\n"
                    f"**Columns**: {c1}, {c2}, {n}\n"
                    f"**Explanation**: Group {col_label(n)} by {col_label(c1)} and {col_label(c2)} to find "
                    f"interaction effects and multi-dimensional patterns."
                ),
                "datasets": [dataset_name],
                "goal": f"Multi-dimensional analysis of {col_label(n)} by {col_label(c1)} and {col_label(c2)}",
                "columns": [c1, c2, n],
                "insight": f"Interaction effects between {col_label(c1)} and {col_label(c2)} on {col_label(n)}",
            })

        proposals.extend(local)
        if len(proposals) >= 3:
            break

    return proposals[:3]


async def _handle_suggest(
    session_id: str,
    message: str,
    dataset_names: list[str],
    datasets_data: list[dict],
    attached_aims: list[str],
    enrichment_block: str = "",
    aim_descriptions: dict[str, str] | None = None,
    session_state: dict | None = None,
    language: str = "en",
):
    """SUGGEST route: LLM proposes 3 exploration ideas (no SQL)."""
    set_progress(session_id, "building_context", "running", "Analyzing dataset schema...")
    context = await _build_context(dataset_names, datasets_data, attached_aims, aim_descriptions)
    set_progress(session_id, "building_context", "done", f"{len(datasets_data)} datasets analyzed")

    set_progress(session_id, "llm", "running", "Generating analysis suggestions...")
    system_prompt = suggest_prompt(context=context, language=language)
    real_dataset_names = [ds.get("dataset_name", "?") for ds in datasets_data]
    if len(real_dataset_names) > 1:
        system_prompt += (
            f"\n\n## Multi-Dataset Note\n"
            f"Multiple datasets are attached ({', '.join(real_dataset_names)}). Make sure at least one "
            f"of the 3 suggestions combines two or more of these datasets (using the join hints above) "
            f"and explains in its Explanation field exactly how they connect."
        )
    if enrichment_block:
        system_prompt += f"\n\n## Previous Context\n{enrichment_block}"
    raw = await generate_llm_response(
        system_prompt=system_prompt,
        question=message,
    )
    set_progress(session_id, "llm", "done", "Suggestions generated")

    # Include table names alongside user-facing dataset names for proposal validation
    table_names = [ds.get("table", "") for ds in datasets_data if ds.get("table")]
    known_datasets = list(set(dataset_names + table_names))
    known_columns = {
        c.get("name", "")
        for ds in datasets_data
        for c in ds.get("column_definitions", [])
        if c.get("name")
    }
    proposals = parse_numbered_suggestions(raw, known_datasets=known_datasets, known_columns=known_columns)

    # Fallback: if all proposals were stripped as invalid, generate rule-based ones
    if not proposals:
        proposals = _fallback_aim_suggestions(datasets_data)

    # Build the "what each dataset offers" preamble deterministically — the LLM
    # reliably ignores a prompt-only ask for this, so we render it ourselves.
    if len(real_dataset_names) > 1:
        prop_lines = []
        for ds in datasets_data:
            cols = ds.get("column_definitions", [])
            col_names = [c.get("name", "") for c in cols if c.get("name")][:5]
            role = ds.get("role") or ""
            label = f"{ds.get('dataset_name', '?')}" + (f" ({role})" if role else "")
            prop_lines.append(f"- **{label}**: {', '.join(col_names)}")
        properties_block = "**Dataset Properties**\n" + "\n".join(prop_lines)
        raw = f"{properties_block}\n\n{raw}"

    return {
        "agent_message": raw,
        "result_uuid": None,
        "query_result": None,
        "aim_proposals": proposals,
    }


async def _handle_focus_multi(
    session_id: str,
    message: str,
    dataset_names: list[str],
    datasets_data: list[dict],
    attached_aims: list[str],
    enrichment_block: str = "",
    aim_descriptions: dict[str, str] | None = None,
    language: str = "en",
):
    """Multiple aims attached: run one focused query per aim, then synthesize a combined view."""
    deep_iterations = []
    per_aim_summaries = []

    aim_descriptions = aim_descriptions or {}
    for idx, aim in enumerate(attached_aims):
        set_progress(session_id, f"aim_{idx}", "running", f"Aim {idx+1}/{len(attached_aims)}: {aim[:50]}")
        context = await _build_context(dataset_names, datasets_data, [aim], aim_descriptions)
        system_prompt = focus_prompt(context=context, language=language)
        if enrichment_block:
            system_prompt += f"\n\n## Previous Context\n{enrichment_block}"
        desc = aim_descriptions.get(aim, "")
        aim_question = f"{message}\n\nFocus specifically on this aim: {aim}" + (f" — {desc}" if desc else "")
        raw = await generate_llm_response(system_prompt=system_prompt, question=aim_question)

        sql = extract_sql(raw) or extract_sql_fallback(raw)
        if not sql:
            per_aim_summaries.append(f"### {aim}\n{raw}")
            set_progress(session_id, f"aim_{idx}", "done", f"Aim {idx+1}: no SQL generated")
            continue
        set_progress(session_id, f"aim_{idx}", "running", f"Aim {idx+1}: validating & executing...")

        try:
            sql = validate_sql(sql)
            result = await execute_sql(sql)
        except Exception as e:
            per_aim_summaries.append(f"### {aim}\nCould not complete this analysis: {str(e)[:200]}")
            set_progress(session_id, f"aim_{idx}", "done", f"Aim {idx+1}: error — {str(e)[:60]}")
            continue
        set_progress(session_id, f"aim_{idx}", "running", f"Aim {idx+1}: interpreting results...")

        cs = await _build_chart_suggestions(result, datasets_data)
        chart_suggestions = cs.model_dump() if hasattr(cs, "model_dump") else cs

        interpretation = await interpret_results(
            question=aim_question, sql=result.get("sql", ""), result=result, language=language
        )
        deep_iterations.append({
            "iteration": len(deep_iterations),
            "aim": aim,
            "result_uuid": str(uuid.uuid4()),
            "explanation": f"**{aim}**\n\n{interpretation}",
            "sql": result.get("sql", ""),
            "columns": result.get("columns", []),
            "column_types": result.get("column_types", []),
            "rows": result.get("rows", []),
            "row_count": result.get("row_count", 0),
            "chart_suggestions": chart_suggestions,
        })
        per_aim_summaries.append(f"### {aim}\n{interpretation}")
        set_progress(session_id, f"aim_{idx}", "done", f"Aim {idx+1}: complete")

    combined_prompt = (
        "You analyzed multiple research aims on the same datasets. Below are the individual findings.\n\n"
        + "\n\n".join(per_aim_summaries)
        + "\n\nWrite a short combined synthesis (3-5 sentences): how do these aims relate to each other, "
        "what does looking at them together reveal that looking at each alone would not, and suggest one "
        "new combined analysis idea that connects them."
    )
    combined_msg = await generate_llm_response(
        system_prompt="You are a data analyst assistant synthesizing multiple related analyses into one combined narrative." + language_instruction(language),
        question=combined_prompt,
    )

    result_uuid = str(uuid.uuid4()) if deep_iterations else None
    return {
        "agent_message": combined_msg,
        "result_uuid": result_uuid,
        "query_result": None,
        "deep_iterations": deep_iterations,
    }


async def _handle_focus(
    session_id: str,
    message: str,
    dataset_names: list[str],
    datasets_data: list[dict],
    attached_aims: list[str],
    enrichment_block: str = "",
    aim_descriptions: dict[str, str] | None = None,
    session_state: dict | None = None,
    language: str = "en",
):
    """FOCUS route: agentic tool-calling loop (query fresh data or recall a previously
    fetched result in this session) for a single aim; delegates to _handle_focus_multi
    for multiple aims."""
    set_progress(session_id, "building_context", "running", "Analyzing dataset schema...")
    if len(attached_aims) > 1:
        return await _handle_focus_multi(
            session_id=session_id,
            message=message,
            dataset_names=dataset_names,
            datasets_data=datasets_data,
            attached_aims=attached_aims,
            enrichment_block=enrichment_block,
            aim_descriptions=aim_descriptions,
            language=language,
        )

    # Auto-recall: if this exact aim+datasets combo already has a successful
    # focus result in this session, return the cached result without calling
    # the LLM at all — avoids re-hallucination on re-runs.
    if session_state:
        session_turns = session_state.get("turns", [])
        for t in reversed(session_turns):
            if (t.get("route") == "focus"
                and t.get("aims") == attached_aims
                and t.get("datasets") == dataset_names
                and t.get("result_uuid")):
                return {
                    "agent_message": t.get("agent", ""),
                    "result_uuid": t["result_uuid"],
                    "query_result": None,
                }

    # Agentic tool-calling loop (handles everything — simple queries, deep-dives, comprehensive analysis)
    set_progress(session_id, "building_context", "running", "Analyzing dataset schema...")
    context = await _build_context(dataset_names, datasets_data, attached_aims, aim_descriptions, include_samples=False)
    set_progress(session_id, "building_context", "done", f"{len(datasets_data)} datasets analyzed")

    set_progress(session_id, "focus_agent", "running", "Running analysis agent...")
    agent_result = await run_focus_agent(
        message=message,
        context=context,
        attached_aims=attached_aims,
        enrichment_block=enrichment_block,
        session_state=session_state or {},
        datasets_data=datasets_data,
        language=language,
        on_progress=lambda step, status, detail="": set_progress(session_id, f"agent_{step}", status, detail),
    )

    result = agent_result["query_result"]
    if result is None:
        set_progress(session_id, "focus_agent", "done", "Analysis complete (no data query)")
        return {
            "agent_message": agent_result["agent_message"],
            "result_uuid": None,
            "query_result": None,
        }
    set_progress(session_id, "focus_agent", "done", "Analysis complete")

    set_progress(session_id, "building_charts", "running", "Building chart suggestions...")
    chart_suggestions = await _build_chart_suggestions(result, datasets_data)
    result_with_charts = {**result, "chart_suggestions": chart_suggestions}
    set_progress(session_id, "building_charts", "done", "Charts ready")

    result_uuid = str(uuid.uuid4())
    return {
        "agent_message": agent_result["agent_message"],
        "result_uuid": result_uuid,
        "query_result": result_with_charts,
    }


@router.post("/messages", response_model=MessageResponse)
async def send_message(req: MessageRequest):
    """Handle a user message — route via LLM classification into DIRECT/SUGGEST/FOCUS/DEEP."""
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="message is required")

    async with AsyncSessionLocal() as db:
        from sqlalchemy import select
        result = await db.execute(
            select(ManagerSession).where(ManagerSession.session_id == req.session_id)
        )
        session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    expected_version = session.version

    dataset_names = [d.strip() for d in req.line_name.split(",") if d.strip()]

    # Guard: RESEARCH mode with no attachments → early return (no LLM call)
    if req.enrichment_mode == "research" and not req.attached_aims and not dataset_names:
        return MessageResponse(
            session_id=req.session_id,
            agent_message="Please attach a dataset or aim, or switch to SUMMARY mode.",
            route="direct",
        )
    if req.enrichment_mode == "research" and not dataset_names:
        return MessageResponse(
            session_id=req.session_id,
            agent_message="Please select at least one dataset to work with. Search and attach datasets from the search bar above. (Aims are attached but need datasets to execute.)",
            route="direct",
        )

    datasets_data = []
    async with AsyncSessionLocal() as db:
        from sqlalchemy import select, or_
        result = await db.execute(
            select(GlobalRegistry).where(
                or_(
                    GlobalRegistry.dataset_name.in_(dataset_names),
                    GlobalRegistry.line_name.in_(dataset_names),
                ),
                GlobalRegistry.status == "active",
            )
        )
        for reg in result.scalars().all():
            sc = reg.source_config or {}
            datasets_data.append({
                "dataset_name": reg.dataset_name,
                "description": reg.description,
                "column_definitions": reg.column_definitions,
                "join_hints": reg.join_hints,
                "suggested_aims": reg.suggested_aims,
                "table": sc.get("table", reg.dataset_name),
                "backend": "pg",
            })

    # Merge in the user's personal (uploaded CSV) datasets, if any of the attached
    # names match — kept in a separate table from global_registry, tagged so
    # query execution knows to hit the user's SQLite file instead of Postgres.
    user_datasets = await fetch_active_user_datasets(session.user_id, dataset_names)
    datasets_data.extend(user_datasets)

    # Check for unresolvable dataset names
    resolved_names = {d["dataset_name"] for d in datasets_data}
    unresolved = [n for n in dataset_names if n not in resolved_names]
    if unresolved:
        logger.warning("Unresolvable dataset names in request", extra={"unresolved": unresolved, "session_id": req.session_id})
        if not datasets_data and req.enrichment_mode == "research":
            return MessageResponse(
                session_id=req.session_id,
                agent_message=f"No datasets found for: {', '.join(unresolved)}. Please attach available datasets.",
                route="direct",
            )

    # If SUMMARY mode, skip routing and use existing summarization flow
    if req.enrichment_mode == "summary":
        enrichment_block = ""
        if req.enrichment_mode and req.history is not None:
            enrichment_block = build_enrichment_block(
                state=dict(session.state_json or {}),
                attached_aims=req.attached_aims,
                attached_datasets=dataset_names,
                mode=req.enrichment_mode,
            )
        # Always append conversation history from stored turns
        turns = (session.state_json or {}).get("turns", [])
        conv_history = build_conversation_history(turns)
        if conv_history:
            if enrichment_block:
                enrichment_block += "\n\n## Conversation History\n" + conv_history
            else:
                enrichment_block = "## Conversation History\n" + conv_history
        if enrichment_block:
            agent_msg = await generate_chat_response(
                message=req.message,
                dataset_names=dataset_names,
                datasets_data=datasets_data,
                enrichment_block=enrichment_block,
                enrichment_mode=req.enrichment_mode,
                language=req.language,
            )
        else:
            history = req.history or []
            agent_msg = await generate_chat_response(
                message=req.message,
                dataset_names=dataset_names,
                datasets_data=datasets_data,
                history=history,
                enrichment_mode=req.enrichment_mode,
                language=req.language,
            )

        aim_proposals_raw = await extract_aims_from_text(agent_msg, dataset_names)
        aim_proposals = [AimProposal(**a) for a in aim_proposals_raw if isinstance(a, dict)]
        analysis_actions_raw = await extract_analysis_actions(agent_msg, dataset_names) if dataset_names else []
        analysis_actions = [AnalysisAction(**a) for a in analysis_actions_raw if isinstance(a, dict)]

        # Save turn
        async with AsyncSessionLocal() as db:
            from sqlalchemy import select
            row = (await db.execute(
                select(ManagerSession).where(
                    ManagerSession.session_id == req.session_id,
                    ManagerSession.version == expected_version
                )
            )).scalar_one_or_none()
            if not row:
                raise HTTPException(status_code=409, detail="Concurrent modification detected. Please retry.")
            state = dict(row.state_json or {})
            turns = list(state.get("turns", []))
            turn_entry = {
                "user": req.message,
                "agent": agent_msg,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "aims": req.attached_aims,
                "datasets": dataset_names,
            }
            if analysis_actions_raw:
                turn_entry["analysis_actions"] = analysis_actions_raw
            turns.append(turn_entry)
            state["turns"] = turns
            existing = list(state.get("aim_proposals", []))
            for ap in aim_proposals_raw:
                if isinstance(ap, dict) and ap.get("aim") and not any(
                    e.get("aim") == ap["aim"] for e in existing
                ):
                    existing.append(ap)
            state["aim_proposals"] = existing
            row.state_json = state
            row.version += 1
            row.updated_at = datetime.now(timezone.utc)
            if len(turns) == 1 and re.match(r"^Session [a-f0-9]{8}$", row.title or ""):
                new_title = req.message.strip()[:50]
                if new_title:
                    row.title = new_title
            await db.commit()

        return MessageResponse(
            session_id=req.session_id,
            turn_index=0,
            agent_message=agent_msg,
            analysis_actions=analysis_actions,
            done=True,
            aim_proposals=aim_proposals,
            route="summary",
        )

    # RESEARCH mode: classify route and dispatch
    set_progress(req.session_id, "classifying", "running", "Classifying your question...")
    if req.route_override:
        route = req.route_override.lower()
    else:
        route = await classify_route(question=req.message, attached_aims=req.attached_aims)
    set_progress(req.session_id, "classifying", "done", f"Route: {route.upper()}")

    session_state = dict(session.state_json or {})
    enrichment_block = build_enrichment_block(
        state=session_state,
        attached_aims=req.attached_aims,
        attached_datasets=dataset_names,
        mode=req.enrichment_mode,
    )

    # Append conversation history from stored turns (not covered by enrichment tags)
    turns = session_state.get("turns", [])
    conv_history = build_conversation_history(turns)
    if conv_history:
        if enrichment_block:
            enrichment_block += "\n\n## Conversation History\n" + conv_history
        else:
            enrichment_block = "## Conversation History\n" + conv_history

    route = route.lower()

    handler_kwargs = dict(
        message=req.message,
        dataset_names=dataset_names,
        datasets_data=datasets_data,
        attached_aims=req.attached_aims,
        enrichment_block=enrichment_block,
        aim_descriptions=req.aim_descriptions,
        session_state=session_state,
        language=req.language,
    )

    set_progress(req.session_id, "processing", "running", f"Running {route.upper()} pipeline...")
    if route == "suggest":
        handler_result = await _handle_suggest(req.session_id, **handler_kwargs)
    else:
        handler_result = await _handle_focus(req.session_id, **handler_kwargs)
    set_progress(req.session_id, "processing", "done", f"{route.upper()} completed")

    agent_msg = handler_result["agent_message"]
    result_uuid = handler_result.get("result_uuid")
    query_result_raw = handler_result.get("query_result")
    handler_proposals = handler_result.get("aim_proposals", [])
    deep_iterations_raw = handler_result.get("deep_iterations", [])

    log_response(route, result_uuid or "", len(handler_proposals))
    log_aims(len(handler_proposals), f"from handler ({route})")
    if result_uuid:
        log_sql("executed", f"result_uuid={result_uuid[:8]}")

    query_result_model = None
    if query_result_raw:
        cs_model = query_result_raw.get("chart_suggestions")
        if isinstance(cs_model, dict):
            cs_model = ChartSuggestions(
                advanced=[ChartConfig(**c) for c in cs_model.get("advanced", [])],
                basic=[ChartConfig(**c) for c in cs_model.get("basic", [])],
            )
        query_result_model = QueryResult(
            sql=query_result_raw.get("sql", ""),
            columns=query_result_raw.get("columns", []),
            column_types=query_result_raw.get("column_types", []),
            rows=query_result_raw.get("rows", []),
            row_count=query_result_raw.get("row_count", 0),
            chart_suggestions=cs_model,
        )

    # Extract proposals/actions from agent message for DIRECT route backward compat
    aim_proposals_raw = await extract_aims_from_text(agent_msg, dataset_names) if route in ("direct",) else []
    if handler_proposals:
        aim_proposals_raw = list(aim_proposals_raw) + list(handler_proposals)
    aim_proposals = [AimProposal(**a) for a in aim_proposals_raw if isinstance(a, dict)]
    # Filter out garbled proposals — must have a real aim name and valid datasets
    known_set = set(dataset_names)
    aim_proposals = [
        p for p in aim_proposals
        if len(p.aim) > 3
        and p.datasets
        and any(ds in known_set for ds in p.datasets)
    ]
    # FOCUS/DIRECT/DEEP routes: extract actions from agent response text via secondary LLM call
    analysis_actions_raw = []
    if dataset_names and route in ("direct", "focus", "deep"):
        analysis_actions_raw = await extract_analysis_actions(agent_msg, dataset_names)
    # SUGGEST route: map parsed proposals directly to analysis_actions (no extra LLM call)
    elif route.lower() == "suggest" and handler_proposals:
        analysis_actions_raw = [
            {"name": p["aim"], "description": p.get("description", ""), "datasets": p.get("datasets", []), "goal": p.get("goal"), "columns": p.get("columns"), "insight": p.get("insight")}
            for p in handler_proposals
            if isinstance(p, dict) and p.get("aim")
        ]
    analysis_actions = [AnalysisAction(**a) for a in analysis_actions_raw if isinstance(a, dict)]

    # Save turn
    async with AsyncSessionLocal() as db:
        from sqlalchemy import select
        row = (await db.execute(
            select(ManagerSession).where(
                ManagerSession.session_id == req.session_id,
                ManagerSession.version == expected_version
            )
        )).scalar_one_or_none()
        if not row:
            raise HTTPException(status_code=409, detail="Concurrent modification detected. Please retry.")
        state = dict(row.state_json or {})
        turns = list(state.get("turns", []))
        turn_entry = {
            "user": req.message,
            "agent": agent_msg,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "aims": req.attached_aims,
            "datasets": dataset_names,
            "route": route,
        }
        if result_uuid:
            turn_entry["result_uuid"] = result_uuid
        if query_result_raw:
            query_result_save = {
                "sql": query_result_raw.get("sql", ""),
                "columns": query_result_raw.get("columns", []),
                "row_count": query_result_raw.get("row_count", 0),
            }
            if query_result_raw.get("chart_suggestions") is not None:
                cs = query_result_raw["chart_suggestions"]
                query_result_save["chart_suggestions"] = cs.model_dump() if hasattr(cs, "model_dump") else cs
            turn_entry["query_result"] = query_result_save
        if deep_iterations_raw:
            turn_entry["deep_iterations"] = deep_iterations_raw
        if analysis_actions_raw:
            turn_entry["analysis_actions"] = analysis_actions_raw
        turns.append(turn_entry)
        state["turns"] = turns
        existing = list(state.get("aim_proposals", []))
        for ap in aim_proposals_raw:
            if isinstance(ap, dict) and ap.get("aim") and not any(
                e.get("aim") == ap["aim"] for e in existing
            ):
                existing.append(ap)
        state["aim_proposals"] = existing

        # Persist full query result (including rows and chart_suggestions) to
        # chat_query_results so the frontend finds it on page reload.
        if result_uuid and query_result_raw:
            chat_results = dict(state.get("chat_query_results", {}))
            chat_result = {
                "sql": query_result_raw.get("sql", ""),
                "columns": query_result_raw.get("columns", []),
                "column_types": query_result_raw.get("column_types", []),
                "rows": query_result_raw.get("rows", []),
                "row_count": query_result_raw.get("row_count", 0),
            }
            if query_result_raw.get("chart_suggestions") is not None:
                cs = query_result_raw["chart_suggestions"]
                chat_result["chart_suggestions"] = cs.model_dump() if hasattr(cs, "model_dump") else cs
            chat_results[result_uuid] = chat_result
            state["chat_query_results"] = chat_results

        row.state_json = state
        row.version += 1
        row.updated_at = datetime.now(timezone.utc)
        if len(turns) == 1 and re.match(r"^Session [a-f0-9]{8}$", row.title or ""):
            new_title = req.message.strip()[:50]
            if new_title:
                row.title = new_title
        await db.commit()

    return MessageResponse(
        session_id=req.session_id,
        turn_index=0,
        agent_message=agent_msg,
        route=route,
        result_uuid=result_uuid,
        query_result=query_result_model,
        analysis_actions=analysis_actions,
        done=True,
        aim_proposals=aim_proposals,
        deep_iterations=deep_iterations_raw,
    )


@router.post("/sessions/{session_id}/summarize-context", response_model=SummarizeContextResponse)
async def summarize_context(session_id: str, req: SummarizeContextRequest):
    """Summarize a set of turns for a given tag. Idempotent — returns existing summary if already covered."""
    if not req.tag or not req.turn_timestamps:
        raise HTTPException(status_code=400, detail="tag and turn_timestamps are required")

    row = await _get_session_owned(session_id, req.user_id or None)

    expected_version = row.version
    state = dict(row.state_json or {})
    timestamp_set = set(req.turn_timestamps)

    # Idempotency check — return existing summary if all timestamps are already covered
    existing = state.get("context_summaries", {}).get(req.tag, [])
    for entry in existing:
        if all(ts in entry.get("turn_timestamps", []) for ts in req.turn_timestamps):
            return SummarizeContextResponse(
                tag=req.tag,
                summary=entry["summary"],
                created_at=entry["created_at"],
            )

    # Fetch turns by timestamps
    turns = state.get("turns", [])
    relevant_turns = [t for t in turns if (t.get("created_at") or t.get("timestamp")) in timestamp_set]
    if not relevant_turns:
        raise HTTPException(status_code=400, detail="No turns found for the given timestamps")

    # Build thread text for LLM
    thread_lines = []
    for t in relevant_turns:
        user_text = (t.get("user") or "")[:200]
        agent_text = (t.get("agent") or "")[:200]
        aims = ", ".join(t.get("aims") or [])
        datasets = ", ".join(t.get("datasets") or [])
        meta = f"[aims: {aims}] [datasets: {datasets}]" if aims or datasets else ""
        thread_lines.append(f"User: {user_text}\nAgent: {agent_text} {meta}")
    thread_text = "\n---\n".join(thread_lines)

    # Call LLM for summary
    summary = await summarize_turns(thread_text)
    if not summary:
        raise HTTPException(status_code=502, detail="Summary generation failed")

    now = datetime.now(timezone.utc).isoformat()
    summary_entry = {
        "turn_timestamps": req.turn_timestamps,
        "summary": summary,
        "created_at": now,
    }

    # Save with optimistic locking
    async with AsyncSessionLocal() as db:
        row = (await db.execute(
            select(ManagerSession).where(
                ManagerSession.session_id == session_id,
                ManagerSession.version == expected_version
            )
        )).scalar_one_or_none()
        if not row:
            raise HTTPException(status_code=409, detail="Concurrent modification detected. Please retry.")

        state = dict(row.state_json or {})
        summaries = dict(state.get("context_summaries", {}))
        tag_list = list(summaries.get(req.tag, []))
        tag_list.append(summary_entry)
        summaries[req.tag] = tag_list
        state["context_summaries"] = summaries
        row.state_json = state
        row.version += 1
        row.updated_at = datetime.now(timezone.utc)
        await db.commit()

    return SummarizeContextResponse(tag=req.tag, summary=summary, created_at=now)
