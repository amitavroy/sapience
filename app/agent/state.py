from dataclasses import dataclass
from typing import Annotated, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


class ConversationState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    reply: str


@dataclass(frozen=True)
class ConversationContext:
    """Per-turn facts the LLM must not control; tools and prompts read them from the runtime."""

    space: str
    user: str
    display_name: str
