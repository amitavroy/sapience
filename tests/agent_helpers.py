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
