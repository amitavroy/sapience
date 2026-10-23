from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph

from app.agent.checkpointer import open_checkpointer
from app.agent.graph import build_graph
from app.agent.state import ConversationContext

# caps the model <-> tools loop within one turn
RECURSION_LIMIT = 12


def thread_id(space: str, user: str) -> str:
    return f"gchat:{space}:{user}"


@asynccontextmanager
async def open_graph() -> AsyncIterator[CompiledStateGraph]:
    """The conversation graph on a checkpointer that lives for the block."""
    async with open_checkpointer() as checkpointer:
        yield build_graph(checkpointer)


async def run_turn(
    graph: CompiledStateGraph, ctx: ConversationContext, message_name: str, text: str
) -> str:
    """Run one user message through the graph and return the reply text."""
    config: RunnableConfig = {
        "configurable": {"thread_id": thread_id(ctx.space, ctx.user)},
        "recursion_limit": RECURSION_LIMIT,
    }
    # the Chat message name as id keeps the human message from being duplicated if re-applied
    state = await graph.ainvoke(
        {"messages": [HumanMessage(text, id=message_name)]}, config, context=ctx
    )
    return state["reply"]
