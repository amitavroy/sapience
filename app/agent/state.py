from dataclasses import dataclass
from typing import Annotated, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

from app.services.retrieval import KnowledgeSearch, RetrievedChunk


class ConversationState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    reply: str
    queries: list[str]  # the rewrite's output for this turn
    probe: list[RetrievedChunk]
    doc_ids: list[int]  # the documents the deep search covers, as graded
    knowledge: list[RetrievedChunk]  # what the agent answers from
    search_outcome: str  # "skipped" | "no_match" | "found"
    pending: dict | None  # the interrupt payload grade built for an ambiguous question
    choice: dict | None  # what the user answered; ask_clarification's resume value


@dataclass(frozen=True)
class ConversationContext:
    """Per-turn facts the LLM must not control; tools and prompts read them from the runtime."""

    space: str
    user: str
    display_name: str
    user_id: int | None = None  # the asker's app user; their collections are found by it
    # runtime context, not state: it is not serializable and the model must not control it
    search: KnowledgeSearch | None = None
