from langchain.agents import create_agent
from langchain.agents.middleware import SummarizationMiddleware
from langchain_core.messages import RemoveMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import REMOVE_ALL_MESSAGES
from langgraph.graph.state import CompiledStateGraph
from langgraph.runtime import Runtime

from app.agent.models import get_model
from app.agent.prompts import system_prompt
from app.agent.state import ConversationContext, ConversationState
from app.agent.tools import TOOLS

MAX_REPLY_CHARS = 8000
TRUNCATED_SUFFIX = "… (truncated)"
# Constants, not env vars, until a deployment needs different values.
SUMMARY_TRIGGER_TOKENS = 8000
SUMMARY_KEEP_MESSAGES = 20


def finalize(state: ConversationState) -> dict:
    text = state["messages"][-1].text
    if len(text) > MAX_REPLY_CHARS:
        text = text[: MAX_REPLY_CHARS - len(TRUNCATED_SUFFIX)] + TRUNCATED_SUFFIX
    return {"reply": text}


def build_graph(checkpointer: BaseCheckpointSaver) -> CompiledStateGraph:
    agent = create_agent(
        model=get_model("chat"),
        tools=TOOLS,
        context_schema=ConversationContext,
        middleware=[
            system_prompt,
            SummarizationMiddleware(
                model=get_model("summary"),
                trigger=("tokens", SUMMARY_TRIGGER_TOKENS),
                keep=("messages", SUMMARY_KEEP_MESSAGES),
            ),
        ],
    )

    async def run_agent(
        state: ConversationState, config: RunnableConfig, runtime: Runtime[ConversationContext]
    ) -> dict:
        result = await agent.ainvoke(state, config, context=runtime.context)
        # A subgraph's output is merged by the parent's add_messages, which never sees the
        # middleware's removals, so summarized messages would stay in the checkpoint. Replace the
        # whole list with what the agent ended up with.
        return {"messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES), *result["messages"]]}

    graph = StateGraph(ConversationState, context_schema=ConversationContext)
    graph.add_node("agent", run_agent)
    graph.add_node("finalize", finalize)
    graph.add_edge(START, "agent")
    graph.add_edge("agent", "finalize")
    graph.add_edge("finalize", END)
    return graph.compile(checkpointer=checkpointer)
