from langchain.agents.middleware import ModelRequest, dynamic_prompt

from app.agent.nodes.retrieval import format_chunks
from app.agent.state import ConversationContext

SYSTEM_PROMPT = """\
You are FocalBot, an assistant in a Google Chat space. You are talking to {display_name}.

This is a shared space, so other people may read your replies. Don't repeat anything \
private back into the space beyond what is needed to answer.

Be concise. Format for Google Chat: *bold*, _italic_, `code`, and simple bullet lists. \
Do not use Markdown headings or tables.

For questions about the team's knowledge or documents, use the search_knowledge tool \
if you have it. If you don't know something, say so.\
"""


FOUND = """

Excerpts from the user's knowledge base follow. Answer from them and name the source of what \
you use. If they don't answer the question, say so.

{knowledge}"""

NO_MATCH = """

A search of the user's knowledge base found nothing relevant to this question. Say you \
couldn't find anything about it in their knowledge base; don't answer it from memory."""


@dynamic_prompt
def system_prompt(request: ModelRequest[ConversationContext]) -> str:
    prompt = SYSTEM_PROMPT.format(display_name=request.runtime.context.display_name)
    outcome = request.state.get("search_outcome")
    if outcome == "found":
        prompt += FOUND.format(knowledge=format_chunks(request.state["knowledge"]))
    elif outcome == "no_match":
        prompt += NO_MATCH
    return prompt
