"""Agent test helpers: a scripted chat model that records what it was asked."""

from types import SimpleNamespace
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import RunnableLambda

from app.services.retrieval import RetrievedChunk


class FakeChatModel(BaseChatModel):
    """Answers from `replies` in order (repeating the last) and records every prompt.

    A reply is text, or a ready AIMessage when the turn needs `tool_calls`."""

    replies: list[str | AIMessage] = ["ok"]
    calls: list[list[BaseMessage]] = []
    # with_structured_output answers: the object (or an exception to raise) by schema class name
    structured: dict[str, Any] = {}
    structured_calls: list[tuple[str, list[BaseMessage]]] = []

    @property
    def _llm_type(self) -> str:
        return "fake"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        self.calls.append(list(messages))
        reply = self.replies[min(len(self.calls), len(self.replies)) - 1]
        message = reply if isinstance(reply, AIMessage) else AIMessage(reply)
        return ChatResult(generations=[ChatGeneration(message=message)])

    def bind_tools(self, tools, **kwargs):
        return self

    def with_structured_output(self, schema, **kwargs):
        name = schema.__name__

        async def answer(messages):
            self.structured_calls.append((name, list(messages)))
            result = self.structured[name]
            if isinstance(result, Exception):
                raise result
            return result

        return RunnableLambda(answer)


def make_chunk(document_id: int, content: str = "body", title: str = "Doc") -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=document_id * 10,
        document_id=document_id,
        title=title,
        source_uri=f"https://example.com/{document_id}",
        content=content,
        distance=0.1,
    )


class FakeSearch:
    """A KnowledgeSearch that records its calls and returns fixed chunks."""

    def __init__(
        self,
        probe: list[RetrievedChunk] | None = None,
        deep: list[RetrievedChunk] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.probe_result = probe or []
        self.deep_result = deep or []
        self.error = error
        self.calls: list[tuple] = []

    async def probe(self, user_id: int, queries: list[str]) -> list[RetrievedChunk]:
        self.calls.append(("probe", user_id, queries))
        if self.error:
            raise self.error
        return self.probe_result

    async def deep_search(
        self, user_id: int, query: str, doc_ids: list[int] | None
    ) -> list[RetrievedChunk]:
        self.calls.append(("deep", user_id, query, doc_ids))
        if self.error:
            raise self.error
        return self.deep_result


class FakeChat:
    """Stands in for GoogleChatClient: records what the app posted."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    async def create_message(self, space: str, text: str) -> str:
        self.sent.append((space, text))
        return f"{space}/messages/1"


class FakeRedis:
    """The Redis calls the chat queue uses, kept in memory (no TTLs: nothing here waits)."""

    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.lists: dict[str, list[str]] = {}

    async def set(self, key, value, condition=None, ex=None):
        if condition is not None and key in self.values:
            return None
        self.values[key] = value
        return True

    async def rpush(self, key, elements) -> int:
        self.lists.setdefault(key, []).extend(elements)
        return len(self.lists[key])

    async def lindex(self, key, index):
        items = self.lists.get(key, [])
        return items[index] if items else None

    async def llen(self, key) -> int:
        return len(self.lists.get(key, []))

    async def delete(self, keys) -> int:
        return sum(self.values.pop(k, None) is not None for k in keys)

    async def eval(self, script, keys, args):
        """Runs the three token-guarded scripts of conversation_queue by what they do."""
        if self.values.get(keys[0]) != args[0]:
            return 0
        if "'lpop'" in script:
            self.lists[keys[1]].pop(0)
        elif "'del'" in script:
            del self.values[keys[0]]
        return 1


class FakeGraph:
    """Just enough of a compiled graph for process_item when run_turn is faked out."""

    def __init__(self, checkpoint: str | None = None, pending: str | None = None) -> None:
        self.checkpoint = checkpoint
        self.pending = pending  # the clarification id the thread is paused on, if any
        self.checkpointer = self
        self.deleted: list[str] = []
        self.updates: list[tuple] = []

    async def aget_state(self, config):
        configurable = {"thread_id": config["configurable"]["thread_id"]}
        if self.checkpoint:
            configurable["checkpoint_id"] = self.checkpoint
        interrupts = (
            [SimpleNamespace(value={"clarification_id": self.pending})] if self.pending else []
        )
        snapshot = {"config": {"configurable": configurable}, "interrupts": interrupts}
        return SimpleNamespace(**snapshot)

    async def adelete_thread(self, thread_id: str) -> None:
        self.deleted.append(thread_id)

    async def aupdate_state(self, config, values, as_node=None) -> None:
        self.updates.append((config, values, as_node))


class NullLog:
    """A ConversationLog that records nothing, for tests that are not about the log."""

    async def record_user_message(self, key, message_name, text) -> None: ...

    async def record_reply(self, key, message_name, text, chat_message_name) -> None: ...

    async def finish_user_message(self, key, message_name, text, status, error) -> None: ...

    async def clear_messages(self, key) -> None: ...
