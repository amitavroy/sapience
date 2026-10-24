"""Agent test helpers: a scripted chat model that records what it was asked."""

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult


class FakeChatModel(BaseChatModel):
    """Answers from `replies` in order (repeating the last) and records every prompt."""

    replies: list[str] = ["ok"]
    calls: list[list[BaseMessage]] = []

    @property
    def _llm_type(self) -> str:
        return "fake"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        self.calls.append(list(messages))
        reply = self.replies[min(len(self.calls), len(self.replies)) - 1]
        return ChatResult(generations=[ChatGeneration(message=AIMessage(reply))])

    def bind_tools(self, tools, **kwargs):
        return self


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

    def __init__(self, checkpoint: str | None = None) -> None:
        self.checkpoint = checkpoint
        self.checkpointer = self
        self.deleted: list[str] = []
        self.updates: list[tuple] = []

    async def aget_state(self, config):
        configurable = {"thread_id": config["configurable"]["thread_id"]}
        if self.checkpoint:
            configurable["checkpoint_id"] = self.checkpoint
        return type("Snapshot", (), {"config": {"configurable": configurable}})()

    async def adelete_thread(self, thread_id: str) -> None:
        self.deleted.append(thread_id)

    async def aupdate_state(self, config, values, as_node=None) -> None:
        self.updates.append((config, values, as_node))
