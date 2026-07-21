"""FastAPI routes for the v2 clean-slate manager."""

import re
import uuid
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from resolve import resolve_line_lookup, fetch_datasets, save_task_definition
from aims import generate_chat_response, generate_sql, fix_sql, criticize_sql, extract_aims_from_text, extract_analysis_actions, suggest_charts, _fallback_chart_configs
from llm_client import summarize_turns
from sql_executor import execute_sql
from db.models import GlobalRegistry, ManagerSession
from db.session import AsyncSessionLocal
from config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v2")
settings = get_settings()

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
    enrichment_mode: str = "research"
    history: list[dict] | None = None

class AimProposal(BaseModel):
    aim: str
    description: str = ""
    datasets: list[str] = []

class AnalysisAction(BaseModel):
    name: str
    description: str = ""
    datasets: list[str] = []

class SummarizeContextRequest(BaseModel):
    tag: str
    turn_timestamps: list[str]

class SummarizeContextResponse(BaseModel):
    tag: str
    summary: str
    created_at: str

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

class ChartConfig(BaseModel):
    chartType: str
    xKey: str
    yKeys: list[str]
    reason: str = ""
    xLabel: str = ""
    yLabel: str = ""
    howToRead: str = ""

class ChartSuggestions(BaseModel):
    advanced: list[ChartConfig] = []
    basic: list[ChartConfig] = []

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

# ── Helpers ──

async def _build_chart_suggestions(result: dict) -> ChartSuggestions | None:
    """Build chart suggestions from SQL result, falling back to rules on failure."""
    if not result.get("columns") or not result.get("rows"):
        return None
    try:
        suggestions_raw = await suggest_charts(
            columns=result["columns"],
            column_types=result.get("column_types", []),
            rows=result["rows"],
        )
        return ChartSuggestions(
            advanced=[ChartConfig(**c) for c in suggestions_raw.get("advanced", [])],
            basic=[ChartConfig(**c) for c in suggestions_raw.get("basic", [])],
        )
    except Exception as chart_err:
        logger.warning("Chart suggestion failed: %s", str(chart_err)[:200])
        fallback = _fallback_chart_configs(
            result["columns"], result.get("column_types", []), result["rows"]
        )
        return ChartSuggestions(
            advanced=[ChartConfig(**c) for c in fallback.get("advanced", [])],
            basic=[ChartConfig(**c) for c in fallback.get("basic", [])],
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
    task_def = {
        "aims": [req.aim],
        "how_we_will_do_it": req.how_we_will_do_it,
        "datasets_used": req.datasets_used,
        "source": "v2_workspace",
    }
    try:
        version = await save_task_definition(req.line_name, settings.default_user_id, task_def)
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
                chart_suggestions = await _build_chart_suggestions(result)
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
        chart_suggestions = await _build_chart_suggestions(result)
    except Exception:
        chart_suggestions = None
    return ExecuteQueryResponse(session_id=req.session_id, **result, chart_suggestions=chart_suggestions)


class CreateSessionRequest(BaseModel):
    title: str | None = None

class UpdateSessionRequest(BaseModel):
    title: str | None = None
    state: dict | None = None

@router.post("/sessions")
async def create_session(body: CreateSessionRequest = None):
    """Create a new session."""
    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    title = body.title if body and body.title else f"Session {session_id[:8]}"
    async with AsyncSessionLocal() as db:
        row = ManagerSession(
            session_id=session_id,
            user_id=settings.default_user_id,
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
    async with AsyncSessionLocal() as db:
        from sqlalchemy import select
        row = (await db.execute(
            select(ManagerSession).where(ManagerSession.session_id == session_id)
        )).scalar_one_or_none()
        if not row:
            raise HTTPException(status_code=404, detail="Session not found")
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
async def list_sessions():
    """List all sessions."""
    async with AsyncSessionLocal() as db:
        from sqlalchemy import select
        result = await db.execute(
            select(ManagerSession).order_by(ManagerSession.updated_at.desc()).limit(50)
        )
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
async def get_session(session_id: str):
    """Get session details."""
    async with AsyncSessionLocal() as db:
        from sqlalchemy import select
        result = await db.execute(
            select(ManagerSession).where(ManagerSession.session_id == session_id)
        )
        row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Session not found")
    state = row.state_json or {}
    return {
        "session_id": row.session_id,
        "title": row.title,
        "phase": row.phase,
        "status": row.status,
        "state": state,
        "turns": state.get("turns", []),
    }

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

@router.post("/messages", response_model=MessageResponse)
async def send_message(req: MessageRequest):
    """Handle a user message — build context from selected datasets and return LLM response."""
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
        agent_msg = "Please attach a dataset or aim, or switch to SUMMARY mode."
    elif req.enrichment_mode == "research" and not dataset_names:
        agent_msg = "Please select at least one dataset to work with. Search and attach datasets from the search bar above."
    else:
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
                    "description": reg.description,
                    "column_definitions": reg.column_definitions,
                    "join_hints": reg.join_hints,
                    "suggested_aims": reg.suggested_aims,
                })

        # Build enrichment block when mode is set, replacing history
        enrichment_block = ""
        if req.enrichment_mode and req.history is not None:
            enrichment_block = build_enrichment_block(
                state=dict(session.state_json or {}),
                attached_aims=req.attached_aims,
                attached_datasets=dataset_names,
                mode=req.enrichment_mode,
            )
        if enrichment_block:
            logger.info("Using enrichment block (%d chars) instead of history", len(enrichment_block))
            if req.history:
                logger.warning("Ignoring history (len=%d) — enrichment_mode is set", len(req.history))
            agent_msg = await generate_chat_response(
                message=req.message,
                dataset_names=dataset_names,
                datasets_data=datasets_data,
                enrichment_block=enrichment_block,
                enrichment_mode=req.enrichment_mode,
            )
        else:
            history = req.history or []
            agent_msg = await generate_chat_response(
                message=req.message,
                dataset_names=dataset_names,
                datasets_data=datasets_data,
                history=history,
                enrichment_mode=req.enrichment_mode,
            )

    # Extract structured aim proposals from the response
    aim_proposals_raw = await extract_aims_from_text(agent_msg, dataset_names)
    aim_proposals = [AimProposal(**a) for a in aim_proposals_raw if isinstance(a, dict)]

    # Extract interactive analysis actions from the response
    analysis_actions_raw = await extract_analysis_actions(agent_msg, dataset_names) if dataset_names else []
    analysis_actions = [AnalysisAction(**a) for a in analysis_actions_raw if isinstance(a, dict)]

    # Save turn + proposals + actions to session state
    async with AsyncSessionLocal() as db:
        from sqlalchemy import select
        row = (await db.execute(
            select(ManagerSession).where(
                ManagerSession.session_id == req.session_id,
                ManagerSession.version == expected_version
            )
        )).scalar_one_or_none()
        if not row:
            raise HTTPException(
                status_code=409,
                detail="Concurrent modification detected. Please retry."
            )
        if row:
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

            # Accumulate aim proposals in session state
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

            # Auto-name on first message
            if len(turns) == 1 and re.match(r"^Session [a-f0-9]{8}$", row.title or ""):
                new_title = req.message.strip()[:50]
                if new_title:
                    row.title = new_title

            await db.commit()

    return MessageResponse(
        session_id=req.session_id,
        turn_index=0,
        agent_message=agent_msg,
        phase="chat",
        status="active",
        analysis_actions=analysis_actions,
        done=True,
        aim_proposals=aim_proposals,
    )


@router.post("/sessions/{session_id}/summarize-context", response_model=SummarizeContextResponse)
async def summarize_context(session_id: str, req: SummarizeContextRequest):
    """Summarize a set of turns for a given tag. Idempotent — returns existing summary if already covered."""
    if not req.tag or not req.turn_timestamps:
        raise HTTPException(status_code=400, detail="tag and turn_timestamps are required")

    async with AsyncSessionLocal() as db:
        from sqlalchemy import select
        row = (await db.execute(
            select(ManagerSession).where(ManagerSession.session_id == session_id)
        )).scalar_one_or_none()

    if not row:
        raise HTTPException(status_code=404, detail="Session not found")

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
