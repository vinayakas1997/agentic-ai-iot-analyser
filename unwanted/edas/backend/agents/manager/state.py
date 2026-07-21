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

    missing: list[str]

    line_context: dict | None

    plan: dict | None

    phase: str



    chat_history: Annotated[list, add_messages]

    task_confirmed: bool

    task_definition: dict | None

    planner_payload: dict | None



    agent_message: str

    message_next_step: str | None

    client: str

    error: str | None

    wants_suggested_aims: bool



    analysis_proposals: list[dict] | None

    explore_phase: str | None

    aim_exploration: dict | None

    explore_context: dict | None

    dataset_context: dict | None

    registry_sync_target: str | None

    time_context: dict | None

    session_inventory: dict | None

    session_intent: str | None

    verification_context: dict | None

    reuse_alias: str | None



    saved_plans: list[dict] | None

    session_goal: str | None

    user_explore_intent: str | None

    scope_selection: str | None

    scope_pending: bool

    iot_column_wishes: list[dict] | None


