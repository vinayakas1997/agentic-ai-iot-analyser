"""Interactive CLI for the Manager Agent."""

import asyncio
import uuid

from agents.manager.runner import run_manager_agent
from config import get_settings


async def run_cli() -> None:
    settings = get_settings()
    user_id = settings.default_user_id
    session_id = str(uuid.uuid4())

    print("EDAS Manager Agent")
    print("==================")
    print("Hi, welcome. What would you like to analyze?")
    print(f"\nSession: {session_id}")
    print("Type 'quit' or 'exit' to end.\n")

    state: dict | None = None

    while True:
        user_message = input("You: ").strip()
        if user_message.lower() in ("quit", "exit"):
            print("Goodbye.")
            break

        result = await run_manager_agent(
            user_id=user_id,
            session_id=session_id,
            line_name="",
            user_message=user_message,
            existing_state=state,
        )
        state = result

        msg = result.get("agent_message", "")
        if msg:
            print(f"\nManager:\n{msg}\n")

        if result.get("planner_payload"):
            print("(Session complete — planner handoff payload ready.)")
            break


def main() -> None:
    asyncio.run(run_cli())


if __name__ == "__main__":
    main()
