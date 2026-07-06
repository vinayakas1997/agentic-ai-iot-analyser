"""Chat history helpers for multi-turn manager conversations."""

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from agents.manager.config import get_chat_window_turns


def get_recent_chat_messages(
    chat_history: list | None,
    max_turns: int | None = None,
) -> list[BaseMessage]:
    """Return the last N user+assistant pairs from chat history."""
    if not chat_history:
        return []
    window = max_turns if max_turns is not None else get_chat_window_turns()
    max_messages = window * 2
    recent = list(chat_history)[-max_messages:]
    return [m for m in recent if isinstance(m, (HumanMessage, AIMessage))]


def append_turn_to_history(
    chat_history: list | None,
    user_message: str,
    agent_message: str,
) -> list[BaseMessage]:
    """Append one user/agent exchange to chat history."""
    history = list(chat_history or [])
    if user_message.strip():
        history.append(HumanMessage(content=user_message.strip()))
    if agent_message.strip():
        history.append(AIMessage(content=agent_message.strip()))
    return history
