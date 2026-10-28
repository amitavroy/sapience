import asyncio
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from functools import partial

import openai
from coredis import Redis
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command

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
from app.services.retrieval import KnowledgeSearch

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


@dataclass(frozen=True)
class TurnResult:
    """What a turn produced: a reply to post, or a clarifying card (the thread is then paused)."""

    reply: str | None
    # quoted: google_chat imports the tasks that import this module, so it is only bound at runtime
    card: "google_chat_service.ClarificationCard | None" = None


class StaleChoiceError(Exception):
    """A button click for a question that is no longer the pending one; dropped, no reply."""


async def run_turn(
    graph: CompiledStateGraph,
    ctx: ConversationContext,
    message_name: str,
    text: str,
    from_checkpoint: str | None = None,
    choice: dict | None = None,
) -> TurnResult:
    """Run one user event through the graph.

    A thread paused on a clarifying question is resumed, never given fresh input, so no pause is
    left orphaned: a click (`choice`: clarification_id and option) answers it, and a typed
    message goes in as text. `from_checkpoint` starts the turn from that checkpoint, which forks a
    new branch that then becomes the thread's latest. Retries use it to leave a half-finished
    attempt behind.
    """
    config = _config(ctx, from_checkpoint)
    snapshot = await graph.aget_state(config)
    if snapshot.interrupts:
        pending = snapshot.interrupts[0].value
        if choice is not None:
            if choice["clarification_id"] != pending["clarification_id"]:
                raise StaleChoiceError(choice["clarification_id"])
            resume = {"kind": "choice", **choice, "message_name": message_name}
        else:
            resume = {"kind": "text", "text": text, "message_name": message_name}
        state = await graph.ainvoke(Command(resume=resume), config, context=ctx)
    elif choice is not None:  # nothing is waiting for this click
        raise StaleChoiceError(choice["clarification_id"])
    else:
        # the Chat message name as id keeps the human message from being duplicated if re-applied
        state = await graph.ainvoke(
            {"messages": [HumanMessage(text, id=message_name)]}, config, context=ctx
        )
    if state.get("__interrupt__"):
        payload = state["__interrupt__"][0].value
        card = google_chat_service.ClarificationCard.from_payload(payload, ctx.user)
        return TurnResult(reply=None, card=card)
    return TurnResult(reply=state["reply"])


async def choice_is_pending(
    graph: CompiledStateGraph, ctx: ConversationContext, clarification_id: str
) -> bool:
    """Whether this thread is paused on exactly that question (a click on any other is stale)."""
    snapshot = await graph.aget_state(_config(ctx))
    return any(i.value["clarification_id"] == clarification_id for i in snapshot.interrupts)


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
    redis: Redis | None = None,
) -> tuple[str, str]:
    """Run the turn and post the reply or card; returns the text and the Chat message it became.

    A card's text is its question, which is what the conversation log keeps for that turn.
    """
    age = time.time() - item.enqueued_at
    if age > MESSAGE_TTL:
        raise MessageExpiredError(f"waited {int(age)}s in the queue")
    # a click resumes the paused thread; other items do not pass `choice` at all
    extra = (
        {"choice": {"clarification_id": item.clarification_id, "option": item.option}}
        if item.kind == "choice"
        else {}
    )

    async def turn() -> TurnResult:
        if from_checkpoint is None:  # nothing to fork from, so clear what a failed attempt left
            await graph.checkpointer.adelete_thread(thread_id(ctx.space, ctx.user))
        return await run_turn(graph, ctx, item.message_name, item.text, from_checkpoint, **extra)

    result = await _with_retries(turn, "conversation turn", item.space)
    # posting is retried on its own, so a Chat outage does not re-run the model
    if result.card is not None:
        card = result.card
        chat_message_name = await _with_retries(
            lambda: google_chat_service.send_card(chat, item.space, card),
            "card post",
            item.space,
        )
        if redis is not None:  # so a later skip or expiry can edit the card
            await conversation_queue.remember_card(redis, card.clarification_id, chat_message_name)
        return card.question, chat_message_name
    answer = result.reply
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


async def _click_is_current(item: QueueItem, ctx: ConversationContext) -> bool:
    """Whether the click answers the question its thread is paused on.

    Checked before anything is logged or posted, so a dropped click leaves no trace in the
    conversation. If the check itself fails (checkpoint database down) the click goes on to
    the normal path, where the failure ends in the apology.
    """
    try:
        async with open_graph() as graph:
            return await choice_is_pending(graph, ctx, item.clarification_id)
    except Exception as e:
        logger.warning(f"could not check the pending question: {_describe(e)}")
        return True


async def process_item(
    chat: GoogleChatClient,
    log: ConversationLog,
    item: QueueItem,
    search: KnowledgeSearch | None = None,
    redis: Redis | None = None,
) -> None:
    """Handle one queued item; never raises, so the drain can always pop it."""
    if item.kind == "reset":
        await _process_reset(chat, log, item)
        return
    if item.kind not in ("message", "choice"):
        logger.warning(f"unsupported queue item kind={item.kind} space={item.space}")
        return
    ctx = ConversationContext(
        space=item.space,
        user=item.user,
        display_name=item.display_name,
        user_id=item.user_id,
        search=search,
    )
    key = _key(item)
    if item.kind == "choice" and not await _click_is_current(item, ctx):
        # a stale card, a second click or another user's card: no model call, no reply, no log
        logger.info(f"dropping click on a question that is not pending space={item.space}")
        return
    # a click is a user turn like any other: the log and the thread both read "Chose: <label>"
    text = f"Chose: {item.text}" if item.kind == "choice" else item.text
    await _logged("user message", log.record_user_message(key, item.message_name, text))
    try:
        # the graph is opened here, not once per drain: a missing LLM key or an unreachable
        # database must end in the apology, and an idle drain should not open a connection
        async with open_graph() as graph:
            from_checkpoint = await current_checkpoint(graph, ctx)
            try:
                reply, chat_message_name = await _answer(
                    graph, chat, ctx, item, from_checkpoint, redis
                )
            except StaleChoiceError:
                raise
            except Exception:
                try:
                    await record_failure(graph, ctx, item.message_name, text, from_checkpoint)
                except Exception as e:
                    logger.error(f"could not record the failed turn: {_describe(e)}")
                raise
        await _logged("reply", log.record_reply(key, item.message_name, reply, chat_message_name))
        await _logged(
            "outcome",
            log.finish_user_message(key, item.message_name, text, MessageStatus.ANSWERED, None),
        )
    except StaleChoiceError:  # lost the race to an answer the check could not see
        logger.info(f"dropping click on a question that is not pending space={item.space}")
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
            log.finish_user_message(key, item.message_name, text, status, _describe(e)),
        )


async def drain(
    space: str, user: str, log: ConversationLog, search: KnowledgeSearch | None = None
) -> None:
    """Worker entry: run this conversation's queued items, opening the per-task resources."""
    async with (
        conversation_queue.open_redis() as redis,
        google_chat_service.open_chat_client() as chat,
    ):
        await conversation_queue.drain(
            redis, space, user, partial(process_item, chat, log, search=search, redis=redis)
        )
