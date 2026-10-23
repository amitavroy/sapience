from langchain.agents import create_agent
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agent.models import get_model
from app.agent.prompts import system_prompt
from app.agent.state import ConversationContext, ConversationState

MAX_REPLY_CHARS = 8000
TRUNCATED_SUFFIX = "… (truncated)"


def finalize(state: ConversationState) -> dict:
    text = state["messages"][-1].text
    if len(text) > MAX_REPLY_CHARS:
        text = text[: MAX_REPLY_CHARS - len(TRUNCATED_SUFFIX)] + TRUNCATED_SUFFIX
    return {"reply": text}


def build_graph(checkpointer: BaseCheckpointSaver) -> CompiledStateGraph:
    agent = create_agent(
        model=get_model("chat"),
        tools=[],
        context_schema=ConversationContext,
        middleware=[system_prompt],
    )
    graph = StateGraph(ConversationState, context_schema=ConversationContext)
    graph.add_node("agent", agent)
    graph.add_node("finalize", finalize)
    graph.add_edge(START, "agent")
    graph.add_edge("agent", "finalize")
    graph.add_edge("finalize", END)
    return graph.compile(checkpointer=checkpointer)
