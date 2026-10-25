from langchain.tools import ToolRuntime, tool

from app.agent.state import ConversationContext

NO_KNOWLEDGE = "No knowledge base is connected yet."


@tool
def search_knowledge(query: str, runtime: ToolRuntime[ConversationContext]) -> str:
    """Search the team's knowledge base for this space. Use it for questions about the
    team's documents or knowledge."""
    # the space comes from the runtime, never from the model: the LLM must not choose whose
    # knowledge it searches. Real retrieval will filter the collection by it.
    space = runtime.context.space  # noqa: F841
    return NO_KNOWLEDGE
