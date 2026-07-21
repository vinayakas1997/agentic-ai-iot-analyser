from typing import Annotated

from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class ManagerState(TypedDict):
    user_id: str
    session_id: str
    user_message: str
    reference_now: str
    reference_timezone: str

    slots: dict
    line_context: dict | None
    plan: dict | None
    dataset_context: dict | None

    phase: str
    chat_history: Annotated[list, add_messages]
    task_confirmed: bool
    task_definition: dict | None
    planner_payload: dict | None

    agent_message: str
    error: str | None

    analyst_reasoning: str | None
    tool_to_call: str | None
    tool_result: str | None

    saved_plans: list[dict] | None
    session_goal: str | None

    analysis_proposals: list[dict] | None
    selected_proposal_index: int | None
    custom_aims: list[dict] | None
    explore_phase: str | None
    explore_iteration: int
    seen_proposal_titles: list[str]
    session_intent: str | None
    verification_context: dict | None
    reuse_alias: str | None
    scope_selection: str | None
    scope_pending: bool
    iot_column_wishes: list[dict] | None
    session_inventory: dict | None
    explore_context: dict | None
    aim_exploration: dict | None
    user_explore_intent: str | None
    selected_suggested_aim: str | None

    tool_call_count: int
    tool_call_history: list[str]
    proposal_counter: int
