# ============================================================
# EDAS — Manager Agent (LangGraph)
# ============================================================
# Flow:
#   check_task_registry
#       ↓
#   route_task (conditional)
#       ├── known   → load_context → confirm_or_update
#       └── unknown → check_schema_registry
#                         ↓
#                     route_schema (conditional)
#                         ├── exists  → load_schema → discuss_task
#                         └── missing → ask_user_schema
#                                           ↓
#                                       validate_schema (Research Agent)
#                                           ↓
#                                       save_schema → discuss_task
#                                           ↓
#                                       chat_loop ←─┐
#                                           ↓        │ not confirmed
#                                       confirm_task─┘
#                                           ↓
#                                       save_task_definition
#                                           ↓
#                                       send_to_research → END
# ============================================================

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Annotated, Any

import asyncpg
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from bus.publisher import publish
from bus.subscriber import subscribe


# ─────────────────────────────────────────────
# LLM Client (vLLM on DGX Spark via Atlas)
# ─────────────────────────────────────────────
import os

llm = ChatOpenAI(
    base_url=os.getenv("VLLM_BASE_URL", "http://192.168.1.101:8009/v1"),
    api_key="not-needed",
    model=os.getenv("MANAGER_MODEL", "qwen3-35b"),
    temperature=0.1,
    max_tokens=2048,
)


# ─────────────────────────────────────────────
# State Definition
# ─────────────────────────────────────────────
class ManagerState(TypedDict):
    # identity
    user_id:             str
    session_id:          str
    line_name:           str

    # phase 1 — task registry
    task_known:          bool
    task_versions:       list[dict]
    selected_version:    int
    existing_definition: dict | None

    # phase 2 — schema registry
    schema_known:        bool
    schema:              dict | None
    schema_verified:     bool
    schema_errors:       list[str]

    # phase 3 — task discussion
    task_definition:     dict | None
    chat_history:        Annotated[list, add_messages]
    task_confirmed:      bool

    # routing + messaging
    next:                str
    user_message:        str
    agent_message:       str       # message to send back to user
    error:               str | None


# ─────────────────────────────────────────────
# DB Helpers
# ─────────────────────────────────────────────
async def get_db():
    return await asyncpg.connect(os.getenv("DATABASE_URL"))


async def fetch_task_versions(line_name: str) -> list[dict]:
    conn = await get_db()
    try:
        rows = await conn.fetch(
            """
            SELECT id, line_name, alias_name, version,
                   task_definition, creator, created_at, updated_at
            FROM task_registry
            WHERE line_name = $1
            ORDER BY version DESC
            """,
            line_name,
        )
        return [dict(r) for r in rows]
    finally:
        await conn.close()


async def fetch_schema(line_name: str) -> dict | None:
    conn = await get_db()
    try:
        row = await conn.fetchrow(
            """
            SELECT * FROM schema_registry
            WHERE line_name = $1 AND verified = TRUE
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            line_name,
        )
        return dict(row) if row else None
    finally:
        await conn.close()


async def save_schema(line_name: str, schema: dict, user_id: str):
    conn = await get_db()
    try:
        await conn.execute(
            """
            INSERT INTO schema_registry
                (line_name, source_type, table_name, column_definitions, verified, verified_by)
            VALUES ($1, $2, $3, $4, TRUE, $5)
            ON CONFLICT (line_name)
            DO UPDATE SET
                column_definitions = EXCLUDED.column_definitions,
                verified           = TRUE,
                verified_by        = EXCLUDED.verified_by,
                updated_at         = NOW()
            """,
            line_name,
            schema.get("source_type"),
            schema.get("table_name"),
            json.dumps(schema.get("column_definitions", [])),
            user_id,
        )
    finally:
        await conn.close()


async def save_task_definition(state: ManagerState):
    conn = await get_db()
    try:
        # get current max version for this line
        row = await conn.fetchrow(
            "SELECT COALESCE(MAX(version), 0) as max_v FROM task_registry WHERE line_name = $1",
            state["line_name"],
        )
        new_version = row["max_v"] + 1
        await conn.execute(
            """
            INSERT INTO task_registry
                (line_name, alias_name, creator, version, task_definition, status)
            VALUES ($1, $2, $3, $4, $5, 'active')
            """,
            state["line_name"],
            state["task_definition"].get("alias_name", state["line_name"]),
            state["user_id"],
            new_version,
            json.dumps(state["task_definition"]),
        )
    finally:
        await conn.close()


# ─────────────────────────────────────────────
# Node 1 — Check Task Registry
# ─────────────────────────────────────────────
async def check_task_registry(state: ManagerState) -> ManagerState:
    """Check if this line/machine has been analyzed before."""
    versions = await fetch_task_versions(state["line_name"])
    return {
        **state,
        "task_known": len(versions) > 0,
        "task_versions": versions,
    }


# ─────────────────────────────────────────────
# Node 2a — Load Existing Context (known path)
# ─────────────────────────────────────────────
async def load_context(state: ManagerState) -> ManagerState:
    """Load the latest task definition for this line."""
    latest = state["task_versions"][0]  # sorted DESC, first = latest
    return {
        **state,
        "selected_version": latest["version"],
        "existing_definition": latest["task_definition"],
        "agent_message": (
            f"I found {len(state['task_versions'])} previous analysis version(s) for "
            f"**{state['line_name']}**.\n\n"
            f"Latest version: **v{latest['version']}** "
            f"(created {latest['created_at'].strftime('%Y-%m-%d')})\n\n"
            f"**Existing aims:**\n"
            + "\n".join(
                f"- {aim}"
                for aim in latest["task_definition"].get("aims", [])
            )
            + "\n\nWould you like to:\n"
            "1. Use this existing analysis\n"
            "2. Add new analysis on top\n"
            "3. Start fresh\n\n"
            "Please reply with 1, 2, or 3."
        ),
    }


# ─────────────────────────────────────────────
# Node 2b — Confirm or Update (known path)
# ─────────────────────────────────────────────
async def confirm_or_update(state: ManagerState) -> ManagerState:
    """User decides what to do with existing analysis."""
    user_reply = state["user_message"].strip()

    if "1" in user_reply:
        # use existing — jump straight to send_to_research
        return {
            **state,
            "task_definition": state["existing_definition"],
            "task_confirmed": True,
            "agent_message": f"Using existing v{state['selected_version']} analysis. Sending to Research Agent...",
        }
    elif "2" in user_reply:
        # add new — go to discuss_task with existing context loaded
        return {
            **state,
            "task_confirmed": False,
            "agent_message": (
                "Great — let's add new analysis. "
                "What additional aims do you have for this line?"
            ),
        }
    else:
        # start fresh — wipe existing, go to discuss_task
        return {
            **state,
            "existing_definition": None,
            "task_confirmed": False,
            "agent_message": (
                "Starting fresh. What analysis would you like to run on "
                f"**{state['line_name']}**?"
            ),
        }


# ─────────────────────────────────────────────
# Node 3 — Check Schema Registry (unknown path)
# ─────────────────────────────────────────────
async def check_schema_registry(state: ManagerState) -> ManagerState:
    """Check if we have verified data source info for this line."""
    schema = await fetch_schema(state["line_name"])
    return {
        **state,
        "schema_known": schema is not None,
        "schema": schema,
    }


# ─────────────────────────────────────────────
# Node 4a — Load Schema (schema exists)
# ─────────────────────────────────────────────
async def load_schema(state: ManagerState) -> ManagerState:
    """Schema already verified — inform user and move to task discussion."""
    schema = state["schema"]
    cols = schema.get("column_definitions", [])
    col_summary = "\n".join(
        f"  - `{c['name']}` ({c['datatype']}): {c['meaning']}"
        for c in cols[:10]  # show max 10
    )
    return {
        **state,
        "agent_message": (
            f"I found verified data source for **{state['line_name']}**:\n\n"
            f"**Source**: `{schema['table_name']}` ({schema['source_type']})\n"
            f"**Columns**:\n{col_summary}\n\n"
            "Now let's define what to analyze. What is your aim?\n"
            "Or type **'suggest'** and I'll propose what we can analyze."
        ),
    }


# ─────────────────────────────────────────────
# Node 4b — Ask User Schema (schema missing)
# ─────────────────────────────────────────────
async def ask_user_schema(state: ManagerState) -> ManagerState:
    """No schema found — ask user to provide data source details."""
    errors = state.get("schema_errors", [])
    error_msg = ""
    if errors:
        error_msg = (
            "\n\n⚠️ Previous schema had issues:\n"
            + "\n".join(f"- {e}" for e in errors)
            + "\n\nPlease correct and resubmit."
        )

    return {
        **state,
        "agent_message": (
            f"I don't have any data source information for **{state['line_name']}** yet."
            f"{error_msg}\n\n"
            "Please provide the following in JSON format:\n\n"
            "```json\n"
            "{\n"
            '  "source_type": "pg" or "csv",\n'
            '  "table_name": "your_table_or_filename",\n'
            '  "column_definitions": [\n'
            '    {"name": "col1", "meaning": "what it means", "datatype": "INT", "format": "YYYYMMDD"},\n'
            '    {"name": "col2", "meaning": "what it means", "datatype": "TEXT", "format": null}\n'
            "  ]\n"
            "}\n"
            "```"
        ),
    }


# ─────────────────────────────────────────────
# Node 5 — Validate Schema (via Research Agent)
# ─────────────────────────────────────────────
async def validate_schema(state: ManagerState) -> ManagerState:
    """
    Parse user provided schema, publish to Research Agent for verification.
    Research Agent checks: table exists, columns match, datatypes correct.
    """
    try:
        # parse JSON from user message
        raw = state["user_message"]
        # extract JSON block if wrapped in markdown
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        schema = json.loads(raw.strip())

        # basic validation before sending to research agent
        required_keys = ["source_type", "table_name", "column_definitions"]
        missing = [k for k in required_keys if k not in schema]
        if missing:
            return {
                **state,
                "schema_verified": False,
                "schema_errors": [f"Missing required field: {k}" for k in missing],
            }

        # publish to research agent for deep verification
        await publish(
            topic="schema.verify",
            user_id=state["user_id"],
            session_id=state["session_id"],
            payload={
                "line_name": state["line_name"],
                "schema": schema,
            },
        )

        # wait for verification result (poll events table)
        # in production this would be event-driven via bus
        # simplified here as direct await
        result = await wait_for_schema_verification(state["session_id"])

        if result["verified"]:
            return {
                **state,
                "schema": schema,
                "schema_verified": True,
                "schema_errors": [],
                "agent_message": (
                    "✅ Schema verified successfully by Research Agent!\n\n"
                    f"**Table**: `{schema['table_name']}`\n"
                    f"**Columns verified**: {len(schema['column_definitions'])}\n\n"
                    "Now let's define the analysis aims. What would you like to analyze?\n"
                    "Or type **'suggest'** for recommendations."
                ),
            }
        else:
            return {
                **state,
                "schema_verified": False,
                "schema_errors": result.get("errors", ["Unknown verification error"]),
            }

    except json.JSONDecodeError:
        return {
            **state,
            "schema_verified": False,
            "schema_errors": ["Invalid JSON format — please check your input"],
        }


async def wait_for_schema_verification(session_id: str, timeout: int = 30) -> dict:
    """Poll events table for schema verification result."""
    conn = await get_db()
    try:
        for _ in range(timeout):
            row = await conn.fetchrow(
                """
                SELECT payload FROM events
                WHERE topic = 'schema.verified'
                AND payload->>'session_id' = $1
                AND status = 'done'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                session_id,
            )
            if row:
                return json.loads(row["payload"])
            await asyncio.sleep(1)
        return {"verified": False, "errors": ["Verification timeout"]}
    finally:
        await conn.close()


# ─────────────────────────────────────────────
# Node 6 — Save Schema
# ─────────────────────────────────────────────
async def save_schema_node(state: ManagerState) -> ManagerState:
    """Save verified schema to schema_registry."""
    await save_schema(state["line_name"], state["schema"], state["user_id"])
    return {**state}


# ─────────────────────────────────────────────
# Node 7 — Discuss Task (chat loop entry)
# ─────────────────────────────────────────────
async def discuss_task(state: ManagerState) -> ManagerState:
    """
    LLM powered conversation to define analysis aims.
    If user says 'suggest' — LLM proposes based on schema.
    """
    user_msg = state["user_message"].lower().strip()
    schema = state.get("schema", {})
    cols = schema.get("column_definitions", []) if schema else []

    if "suggest" in user_msg:
        # LLM suggests analysis based on schema
        col_context = "\n".join(
            f"- {c['name']} ({c['datatype']}): {c['meaning']}"
            for c in cols
        )
        response = await llm.ainvoke([
            SystemMessage(content=(
                "You are a data analysis expert. "
                "Based on the provided column definitions, suggest 4-6 specific, "
                "actionable analysis aims. Be concise and practical."
            )),
            HumanMessage(content=(
                f"Line/Machine: {state['line_name']}\n"
                f"Data columns:\n{col_context}\n\n"
                "Suggest analysis aims."
            )),
        ])
        return {
            **state,
            "agent_message": (
                f"Based on the available data, here are suggested analyses:\n\n"
                f"{response.content}\n\n"
                "Which of these would you like? You can select multiple or describe your own."
            ),
        }

    # normal conversation — LLM helps user refine aim
    history = state.get("chat_history", [])
    messages = [
        SystemMessage(content=(
            f"You are helping define analysis aims for machine/line: {state['line_name']}. "
            "Ask clarifying questions to understand exactly what the user wants to analyze. "
            "Once the aim is clear, summarize it and ask for confirmation with 'confirm'."
        )),
        *history,
        HumanMessage(content=state["user_message"]),
    ]
    response = await llm.ainvoke(messages)
    return {
        **state,
        "chat_history": [*history, HumanMessage(content=state["user_message"]), AIMessage(content=response.content)],
        "agent_message": response.content,
    }


# ─────────────────────────────────────────────
# Node 8 — Confirm Task
# ─────────────────────────────────────────────
async def confirm_task(state: ManagerState) -> ManagerState:
    """Check if user confirmed the task definition."""
    user_msg = state["user_message"].lower().strip()
    confirmed = any(word in user_msg for word in ["confirm", "yes", "ok", "proceed", "go ahead"])

    if confirmed:
        # extract structured task definition from chat history
        history = state.get("chat_history", [])
        response = await llm.ainvoke([
            SystemMessage(content=(
                "Extract the confirmed analysis aims from this conversation "
                "and return ONLY valid JSON in this format:\n"
                '{"aims": ["aim1", "aim2"], "alias_name": "friendly name", '
                '"notes": "any extra context"}'
            )),
            *history,
        ])
        try:
            raw = response.content
            if "```" in raw:
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            task_def = json.loads(raw.strip())
        except Exception:
            task_def = {"aims": [state["user_message"]], "alias_name": state["line_name"]}

        return {
            **state,
            "task_confirmed": True,
            "task_definition": task_def,
            "agent_message": (
                "✅ Task confirmed! Saving and sending to Research Agent...\n\n"
                "**Analysis aims:**\n"
                + "\n".join(f"- {a}" for a in task_def.get("aims", []))
            ),
        }

    return {
        **state,
        "task_confirmed": False,
        "agent_message": (
            "Not confirmed yet. Please refine your aims or type **'confirm'** when ready."
        ),
    }


# ─────────────────────────────────────────────
# Node 9 — Save Task Definition
# ─────────────────────────────────────────────
async def save_task_definition_node(state: ManagerState) -> ManagerState:
    await save_task_definition(state)
    return {**state}


# ─────────────────────────────────────────────
# Node 10 — Send to Research Agent
# ─────────────────────────────────────────────
async def send_to_research(state: ManagerState) -> ManagerState:
    """Publish final task to research.start topic."""
    await publish(
        topic="research.start",
        user_id=state["user_id"],
        session_id=state["session_id"],
        payload={
            "line_name":       state["line_name"],
            "schema":          state["schema"],
            "task_definition": state["task_definition"],
        },
    )
    return {
        **state,
        "agent_message": (
            "🚀 Sent to Research Agent! Analysis is now running.\n"
            "Results will appear in your dashboard as they complete."
        ),
        "next": END,
    }


# ─────────────────────────────────────────────
# Conditional Edge Functions
# ─────────────────────────────────────────────
def route_task(state: ManagerState) -> str:
    return "load_context" if state["task_known"] else "check_schema_registry"


def route_schema(state: ManagerState) -> str:
    return "load_schema" if state["schema_known"] else "ask_user_schema"


def route_after_schema_validation(state: ManagerState) -> str:
    if state["schema_verified"]:
        return "save_schema"
    return "ask_user_schema"  # failed — ask again


def route_task_discussion(state: ManagerState) -> str:
    return "save_task_definition" if state["task_confirmed"] else "discuss_task"


def route_confirm_or_update(state: ManagerState) -> str:
    if state["task_confirmed"]:
        return "send_to_research"
    return "discuss_task"


# ─────────────────────────────────────────────
# Build LangGraph
# ─────────────────────────────────────────────
def build_manager_graph() -> StateGraph:
    graph = StateGraph(ManagerState)

    # add all nodes
    graph.add_node("check_task_registry",    check_task_registry)
    graph.add_node("load_context",           load_context)
    graph.add_node("confirm_or_update",      confirm_or_update)
    graph.add_node("check_schema_registry",  check_schema_registry)
    graph.add_node("load_schema",            load_schema)
    graph.add_node("ask_user_schema",        ask_user_schema)
    graph.add_node("validate_schema",        validate_schema)
    graph.add_node("save_schema",            save_schema_node)
    graph.add_node("discuss_task",           discuss_task)
    graph.add_node("confirm_task",           confirm_task)
    graph.add_node("save_task_definition",   save_task_definition_node)
    graph.add_node("send_to_research",       send_to_research)

    # entry point
    graph.set_entry_point("check_task_registry")

    # edges — fixed
    graph.add_edge("load_context",          "confirm_or_update")
    graph.add_edge("load_schema",           "discuss_task")
    graph.add_edge("ask_user_schema",       "validate_schema")
    graph.add_edge("save_schema",           "discuss_task")
    graph.add_edge("discuss_task",          "confirm_task")
    graph.add_edge("save_task_definition",  "send_to_research")
    graph.add_edge("send_to_research",      END)

    # conditional edges
    graph.add_conditional_edges(
        "check_task_registry",
        route_task,
        {
            "load_context":          "load_context",
            "check_schema_registry": "check_schema_registry",
        },
    )
    graph.add_conditional_edges(
        "check_schema_registry",
        route_schema,
        {
            "load_schema":    "load_schema",
            "ask_user_schema": "ask_user_schema",
        },
    )
    graph.add_conditional_edges(
        "validate_schema",
        route_after_schema_validation,
        {
            "save_schema":    "save_schema",
            "ask_user_schema": "ask_user_schema",
        },
    )
    graph.add_conditional_edges(
        "confirm_task",
        route_task_discussion,
        {
            "save_task_definition": "save_task_definition",
            "discuss_task":         "discuss_task",
        },
    )
    graph.add_conditional_edges(
        "confirm_or_update",
        route_confirm_or_update,
        {
            "send_to_research": "send_to_research",
            "discuss_task":     "discuss_task",
        },
    )

    return graph.compile()


# ─────────────────────────────────────────────
# Manager Agent Entry Point
# ─────────────────────────────────────────────
manager_graph = build_manager_graph()


async def run_manager_agent(
    user_id:     str,
    session_id:  str,
    line_name:   str,
    user_message: str,
    existing_state: dict | None = None,
) -> dict:
    """
    Run one step of the manager agent graph.
    State is persisted externally (pg) between user messages.
    """
    initial_state: ManagerState = {
        # carry over existing state if resuming conversation
        **(existing_state or {}),

        # always update these per invocation
        "user_id":      user_id,
        "session_id":   session_id,
        "line_name":    line_name,
        "user_message": user_message,

        # defaults for first run
        "task_known":          existing_state.get("task_known", False)          if existing_state else False,
        "task_versions":       existing_state.get("task_versions", [])          if existing_state else [],
        "selected_version":    existing_state.get("selected_version", 0)        if existing_state else 0,
        "existing_definition": existing_state.get("existing_definition", None)  if existing_state else None,
        "schema_known":        existing_state.get("schema_known", False)        if existing_state else False,
        "schema":              existing_state.get("schema", None)               if existing_state else None,
        "schema_verified":     existing_state.get("schema_verified", False)     if existing_state else False,
        "schema_errors":       existing_state.get("schema_errors", [])          if existing_state else [],
        "task_definition":     existing_state.get("task_definition", None)      if existing_state else None,
        "chat_history":        existing_state.get("chat_history", [])           if existing_state else [],
        "task_confirmed":      existing_state.get("task_confirmed", False)      if existing_state else False,
        "next":                "",
        "agent_message":       "",
        "error":               None,
    }

    result = await manager_graph.ainvoke(initial_state)
    return result


# ─────────────────────────────────────────────
# Bus Subscriber — listens for task.new events
# ─────────────────────────────────────────────
async def start_manager_subscriber():
    """Subscribe to task.new topic and run manager agent for each event."""
    print("Manager Agent listening on topic: task.new")
    async for event in subscribe("task.new", concurrency_limit=5):
        asyncio.create_task(handle_task_event(event))


async def handle_task_event(event: dict):
    payload = event["payload"]
    result = await run_manager_agent(
        user_id=event["user_id"],
        session_id=event["session_id"],
        line_name=payload["line_name"],
        user_message=payload["user_message"],
        existing_state=payload.get("state"),
    )
    # publish agent response back to frontend via ws.message topic
    await publish(
        topic="ws.message",
        user_id=event["user_id"],
        session_id=event["session_id"],
        payload={
            "agent":   "manager",
            "message": result["agent_message"],
            "state":   result,           # carry state for next turn
        },
    )


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────
if __name__ == "__main__":
    asyncio.run(start_manager_subscriber())
