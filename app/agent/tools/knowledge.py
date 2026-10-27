from langchain.tools import ToolRuntime, tool

from app.agent.nodes.retrieval import format_chunks
from app.agent.state import ConversationContext

NO_KNOWLEDGE = "No knowledge base is connected yet."
NOTHING_FOUND = "Nothing relevant was found in the knowledge base."


@tool
async def search_knowledge(query: str, runtime: ToolRuntime[ConversationContext]) -> str:
    """Search the team's knowledge base. Use it for follow-up questions about the team's
    documents or knowledge, when the excerpts you already have don't cover them."""
    # the asker and the search come from the runtime, never from the model: the LLM must not
    # choose whose collections it searches
    ctx = runtime.context
    if ctx.search is None or ctx.user_id is None:
        return NO_KNOWLEDGE
    chunks = await ctx.search.deep_search(ctx.user_id, query, None)
    return format_chunks(chunks) if chunks else NOTHING_FOUND
