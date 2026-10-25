import asyncio
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from functools import partial

import openai
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph

from app.agent.checkpointer import open_checkpointer
from app.agent.graph import build_graph
from app.agent.state import ConversationContext
from app.core.google_chat_client import (
    GoogleChatClient,
    GoogleChatError,
    GoogleChatNotConfiguredError,
)
from app.core.logger import logger
from app.models.conversation import MessageStatus
from app.services import conversation_queue
from app.services import google_chat as google_chat_service
from app.services.conversation_log import ConversationKey, ConversationLog
from app.services.conversation_queue import QueueItem

# caps the model <-> tools loop within one turn
RECURSION_LIMIT = 12
RETRY_DELAYS = (5, 15, 60)  # seconds before retries 1, 2 and 3
MESSAGE_TTL = 900  # a message older than this when it reaches the head is dropped


def thread_id(space: str, user: str) -> str:
    return f"gchat:{space}:{user}"


@asynccontextmanager
async def open_graph() -> AsyncIterator[CompiledStateGraph]:
    """The conversation graph on a checkpointer that lives for the block."""
    async with open_checkpointer() as checkpointer:
        yield build_graph(checkpointer)


def _config(ctx: ConversationContext, checkpoint_id: str | None = None) -> RunnableConfig:
    configurable = {"thread_id": thread_id(ctx.space, ctx.user)}
    if checkpoint_id:
        configurable["checkpoint_id"] = checkpoint_id
    return {"configurable": configurable, "recursion_limit": RECURSION_LIMIT}


async def current_checkpoint(graph: CompiledStateGraph, ctx: ConversationContext) -> str | None:
    """The thread's latest checkpoint id, or None for a thread with no history yet."""
    state = await graph.aget_state(_config(ctx))
    return state.config["configurable"].get("checkpoint_id")


async def run_turn(
    graph: CompiledStateGraph,
    ctx: ConversationContext,
    message_name: str,
    text: str,
    from_checkpoint: str | None = None,
) -> str:
    """Run one user message through the graph and return the reply text.

    `from_checkpoint` starts the turn from that checkpoint, which forks a new branch that then
    becomes the thread's latest. Retries use it to leave a half-finished attempt behind.
    """
    # the Chat message name as id keeps the human message from being duplicated if re-applied
    state = await graph.ainvoke(
        {"messages": [HumanMessage(text, id=message_name)]},
        _config(ctx, from_checkpoint),
        context=ctx,
    )
    return state["reply"]


async def record_failure(
    graph: CompiledStateGraph,
    ctx: ConversationContext,
    message_name: str,
    text: str,
    from_checkpoint: str | None,
) -> None:
    """Leave the thread as the user saw it: their message and the apology, no half turn."""
    if from_checkpoint is None:  # the thread held nothing before this turn
        await graph.checkpointer.adelete_thread(thread_id(ctx.space, ctx.user))
    reply = google_chat_service.FAILURE_REPLY
    await graph.aupdate_state(
        _config(ctx, from_checkpoint),
        {"messages": [HumanMessage(text, id=message_name), AIMessage(reply)], "reply": reply},
        as_node="finalize",
    )


class MessageExpiredError(Exception):
    pass


def is_retryable(error: Exception) -> bool:
    # APITimeoutError is an APIConnectionError
    if isinstance(error, openai.APIConnectionError | openai.RateLimitError):
        return True
    if isinstance(error, openai.InternalServerError):
        return True
    if isinstance(error, GoogleChatNotConfiguredError):  # no status, but retrying cannot help
        return False
    return isinstance(error, GoogleChatError) and (error.status is None or error.status >= 500)


async def _with_retries[T](call: Callable[[], Awaitable[T]], what: str, space: str) -> T:
    """Retry in place, so the next queued message cannot overtake this one."""
    for delay in RETRY_DELAYS:
        try:
            return await call()
        except Exception as e:
            if not is_retryable(e):
                raise
            logger.warning(f"{what} failed, retrying in {delay}s space={space}: {_describe(e)}")
            await asyncio.sleep(delay)
    return await call()


def _describe(error: Exception) -> str:
    # the type and message only; never the request, which can carry credentials
    return f"{type(error).__name__}: {error}"


async def _answer(
    graph: CompiledStateGraph,
    chat: GoogleChatClient,
    ctx: ConversationContext,
    item: QueueItem,
    from_checkpoint: str | None,
) -> tuple[str, str]:
    """Run the turn and post the reply; returns the reply text and the Chat message it became."""
    age = time.time() - item.enqueued_at
    if age > MESSAGE_TTL:
        raise MessageExpiredError(f"waited {int(age)}s in the queue")

    async def turn() -> str:
        if from_checkpoint is None:  # nothing to fork from, so clear what a failed attempt left
            await graph.checkpointer.adelete_thread(thread_id(ctx.space, ctx.user))
        return await run_turn(graph, ctx, item.message_name, item.text, from_checkpoint)

    answer = await _with_retries(turn, "conversation turn", item.space)
    # posting is retried on its own, so a Chat outage does not re-run the model
    chat_message_name = await _with_retries(
        lambda: google_chat_service.send_message(chat, item.space, answer),
        "reply post",
        item.space,
    )
    return answer, chat_message_name


async def _logged(what: str, write: Awaitable[None]) -> None:
    """The log is a record, not part of the answer: a failed write is reported and skipped."""
    try:
        await write
    except Exception as e:
        logger.error(f"conversation log {what} failed: {_describe(e)}")


async def reset(space: str, user: str) -> None:
    """Forget the agent's memory for this conversation; the conversation log is kept."""
    async with open_checkpointer() as checkpointer:
        await checkpointer.adelete_thread(thread_id(space, user))


def _key(item: QueueItem) -> ConversationKey:
    return ConversationKey(
        channel="google_chat",
        thread_id=thread_id(item.space, item.user),
        space=item.space,
        external_user=item.user,
        display_name=item.display_name,
    )


async def _process_reset(chat: GoogleChatClient, log: ConversationLog, item: QueueItem) -> None:
    key = _key(item)
    cleared = True
    try:
        # not through _logged: saying "cleared" while messages remain would be false. Both deletes
        # are idempotent, so the user can run /reset again after a failure.
        await reset(item.space, item.user)
        await log.clear_messages(key)
        reply = google_chat_service.RESET_REPLY
    except Exception as e:
        cleared = False
        logger.error(f"conversation reset failed space={item.space}: {_describe(e)}")
        reply = google_chat_service.FAILURE_REPLY
    chat_message_name: str | None = None
    try:
        chat_message_name = await _with_retries(
            lambda: google_chat_service.send_message(chat, item.space, reply),
            "reset reply post",
            item.space,
        )
    except Exception as e:
        logger.error(f"could not post the reset reply: {_describe(e)}")
    if cleared:  # the apology records nothing: nothing was cleared
        await _logged(
            "reset reply", log.record_reply(key, item.message_name, reply, chat_message_name)
        )


async def process_item(chat: GoogleChatClient, log: ConversationLog, item: QueueItem) -> None:
    """Handle one queued item; never raises, so the drain can always pop it."""
    if item.kind == "reset":
        await _process_reset(chat, log, item)
        return
    if item.kind != "message":
        logger.warning(f"unsupported queue item kind={item.kind} space={item.space}")
        return
    ctx = ConversationContext(
        space=item.space, user=item.user, display_name=item.display_name, email=item.email
    )
    key = _key(item)
    await _logged("user message", log.record_user_message(key, item.message_name, item.text))
    try:
        # the graph is opened here, not once per drain: a missing LLM key or an unreachable
        # database must end in the apology, and an idle drain should not open a connection
        async with open_graph() as graph:
            from_checkpoint = await current_checkpoint(graph, ctx)
            try:
                reply, chat_message_name = await _answer(graph, chat, ctx, item, from_checkpoint)
            except Exception:
                try:
                    await record_failure(graph, ctx, item.message_name, item.text, from_checkpoint)
                except Exception as e:
                    logger.error(f"could not record the failed turn: {_describe(e)}")
                raise
        await _logged("reply", log.record_reply(key, item.message_name, reply, chat_message_name))
        await _logged(
            "outcome",
            log.finish_user_message(
                key, item.message_name, item.text, MessageStatus.ANSWERED, None
            ),
        )
    except Exception as e:
        logger.error(f"conversation turn failed space={item.space}: {_describe(e)}")
        apology = google_chat_service.FAILURE_REPLY
        apology_name: str | None = None
        try:
            apology_name = await google_chat_service.send_message(chat, item.space, apology)
        except Exception as e2:
            logger.error(f"could not post the failure reply: {_describe(e2)}")
        status = (
            MessageStatus.EXPIRED if isinstance(e, MessageExpiredError) else MessageStatus.FAILED
        )
        await _logged("apology", log.record_reply(key, item.message_name, apology, apology_name))
        await _logged(
            "outcome",
            log.finish_user_message(key, item.message_name, item.text, status, _describe(e)),
        )


async def drain(space: str, user: str, log: ConversationLog) -> None:
    """Worker entry: run this conversation's queued items, opening the per-task resources."""
    async with (
        conversation_queue.open_redis() as redis,
        google_chat_service.open_chat_client() as chat,
    ):
        await conversation_queue.drain(redis, space, user, partial(process_item, chat, log))
