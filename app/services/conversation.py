from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import partial

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph

from app.agent.checkpointer import open_checkpointer
from app.agent.graph import build_graph
from app.agent.state import ConversationContext
from app.core.google_chat_client import GoogleChatClient
from app.core.logger import logger
from app.services import conversation_queue
from app.services import google_chat as google_chat_service
from app.services.conversation_queue import QueueItem

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


async def process_item(chat: GoogleChatClient, item: QueueItem) -> None:
    """Handle one queued item; never raises, so the drain can always pop it."""
    if item.kind != "message":
        logger.warning(f"unsupported queue item kind={item.kind} space={item.space}")
        return
    ctx = ConversationContext(space=item.space, user=item.user, display_name=item.display_name)
    try:
        # the graph is opened here, not once per drain: a missing LLM key or an unreachable
        # database must end in the apology, and an idle drain should not open a connection
        async with open_graph() as graph:
            answer = await run_turn(graph, ctx, item.message_name, item.text)
        await google_chat_service.send_message(chat, item.space, answer)
    except Exception as e:
        # log the type and message only; never the request, which can carry credentials
        logger.error(f"conversation turn failed space={item.space}: {type(e).__name__}: {e}")
        try:
            await google_chat_service.send_message(
                chat, item.space, google_chat_service.FAILURE_REPLY
            )
        except Exception as e2:
            logger.error(f"could not post the failure reply: {type(e2).__name__}: {e2}")


async def drain(space: str, user: str) -> None:
    """Worker entry: run this conversation's queued items, opening the per-task resources."""
    async with (
        conversation_queue.open_redis() as redis,
        google_chat_service.open_chat_client() as chat,
    ):
        await conversation_queue.drain(redis, space, user, partial(process_item, chat))
