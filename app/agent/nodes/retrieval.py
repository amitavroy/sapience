"""Retrieval nodes: decide, rewrite, probe, grade, deep search.

Nodes never open a session: they reach the knowledge base through `ConversationContext.search`.
"""

from typing import Literal

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AnyMessage, HumanMessage, SystemMessage
from langgraph.runtime import Runtime
from langgraph.types import Command
from pydantic import BaseModel, Field

from app.agent.state import ConversationContext, ConversationState
from app.core.logger import logger
from app.services.retrieval import RetrievedChunk

HISTORY_MESSAGES = 3  # messages before the new one the rewrite sees
MAX_QUERIES = 3
GRADE_SNIPPET_CHARS = 300
MAX_DOCS = 3  # documents the deep search covers when the probe is ambiguous (until slice 2)

NEEDS_KB_PROMPT = """\
Decide whether the user's last message needs a search of the team's knowledge base (documents \
and web pages they ingested). Greetings, thanks, small talk and questions about the \
conversation itself do not."""

REWRITE_PROMPT = """\
Write 2 or 3 search queries for the user's last message. Use the earlier messages to resolve \
words like "it" or "that". Each query must stand alone and be broader than the message, so \
related documents are found too."""

GRADE_PROMPT = """\
You see a user's question and the document excerpts a search returned, each with a document id. \
Judge them:
- clear: one document or a few that agree answer it; list their ids in relevant_doc_ids.
- ambiguous: the question could mean several different documents; give 2 or 3 options, each \
with a short label (under 60 characters) and its document ids.
- no_match: none of the excerpts relate to the question."""


class NeedsKb(BaseModel):
    needs_kb: bool


class Rewrite(BaseModel):
    queries: list[str]


class Option(BaseModel):
    label: str = Field(max_length=60)  # shown on a button
    doc_ids: list[int]


class Grade(BaseModel):
    verdict: Literal["clear", "ambiguous", "no_match"]
    relevant_doc_ids: list[int] = []  # for clear
    options: list[Option] = []  # for ambiguous


# what a new turn starts from, so last turn's chunks never leak into this answer
_FRESH = {"queries": [], "probe": [], "knowledge": [], "doc_ids": [], "search_outcome": "skipped"}


def _question(state: ConversationState) -> str:
    return state["messages"][-1].text


def _history(messages: list[AnyMessage]) -> str:
    return "\n".join(f"{m.type}: {m.text}" for m in messages)


def validate_grade(grade: Grade, probe: list[RetrievedChunk]) -> tuple[str, list[int]]:
    """The verdict and doc ids to search, with anything the probe did not return dropped.

    Ambiguous with fewer than two valid options is clear, and clear with no valid ids is
    no_match, so a model slip never reaches the user as an empty question.
    """
    seen = {c["document_id"] for c in probe}
    if grade.verdict == "no_match":
        return "no_match", []
    options = [[d for d in o.doc_ids if d in seen] for o in grade.options]
    options = [ids for ids in options if ids]
    if grade.verdict == "ambiguous" and len(options) >= 2:
        # slice 2 turns these into buttons; until then the nearest documents stand in
        return "clear", list(dict.fromkeys(c["document_id"] for c in probe))[:MAX_DOCS]
    ids = [d for d in grade.relevant_doc_ids if d in seen]
    if grade.verdict == "ambiguous":
        ids = [d for ids in options for d in ids]
    ids = list(dict.fromkeys(ids))
    return ("clear", ids) if ids else ("no_match", [])


def format_chunks(chunks: list[RetrievedChunk]) -> str:
    return "\n\n".join(
        f"[{c['title']}]({c['source_uri']})\n{c['content']}"
        if c["source_uri"]
        else f"[{c['title']}]\n{c['content']}"
        for c in chunks
    )


def retrieval_nodes(classify: BaseChatModel, chat: BaseChatModel) -> dict:
    """The node functions, bound to the models the graph was built with."""
    needs_kb_model = classify.with_structured_output(NeedsKb)
    rewrite_model = chat.with_structured_output(Rewrite)
    grade_model = chat.with_structured_output(Grade)

    async def needs_kb(
        state: ConversationState, runtime: Runtime[ConversationContext]
    ) -> Command[Literal["rewrite", "agent"]]:
        ctx = runtime.context
        if ctx.search is None or ctx.user_id is None:
            return Command(update=_FRESH, goto="agent")
        decision = await needs_kb_model.ainvoke(
            [SystemMessage(NEEDS_KB_PROMPT), HumanMessage(_question(state))]
        )
        logger.info(f"needs_kb={decision.needs_kb}")
        return Command(update=_FRESH, goto="rewrite" if decision.needs_kb else "agent")

    async def rewrite(state: ConversationState) -> dict:
        question = _question(state)
        before = state["messages"][-1 - HISTORY_MESSAGES : -1]
        out = await rewrite_model.ainvoke(
            [
                SystemMessage(REWRITE_PROMPT),
                HumanMessage(f"Earlier messages:\n{_history(before)}\n\nLast message: {question}"),
            ]
        )
        queries = list(dict.fromkeys(q.strip() for q in out.queries if q.strip()))
        return {"queries": queries[:MAX_QUERIES] or [question]}

    async def run_probe(state: ConversationState, runtime: Runtime[ConversationContext]) -> dict:
        ctx = runtime.context
        chunks = await ctx.search.probe(ctx.user_id, state["queries"])
        logger.info(f"probe queries={len(state['queries'])} chunks={len(chunks)}")
        return {"probe": chunks}

    async def grade(
        state: ConversationState,
    ) -> Command[Literal["deep_retrieve", "agent"]]:
        probe = state["probe"]
        if not probe:  # nothing to judge: no model call
            return Command(update={"search_outcome": "no_match"}, goto="agent")
        excerpts = "\n\n".join(
            f"doc {c['document_id']} — {c['title']}\n{c['content'][:GRADE_SNIPPET_CHARS]}"
            for c in probe
        )
        out = await grade_model.ainvoke(
            [
                SystemMessage(GRADE_PROMPT),
                HumanMessage(
                    f"Question: {_question(state)}\nSearch queries: {state['queries']}\n\n"
                    f"{excerpts}"
                ),
            ]
        )
        verdict, doc_ids = validate_grade(out, probe)
        logger.info(f"grade verdict={out.verdict} used={verdict} docs={len(doc_ids)}")
        if verdict == "no_match":
            return Command(update={"search_outcome": "no_match"}, goto="agent")
        return Command(update={"doc_ids": doc_ids}, goto="deep_retrieve")

    async def deep_retrieve(
        state: ConversationState, runtime: Runtime[ConversationContext]
    ) -> dict:
        ctx = runtime.context
        chunks = await ctx.search.deep_search(ctx.user_id, state["queries"][0], state["doc_ids"])
        return {"knowledge": chunks, "search_outcome": "found" if chunks else "no_match"}

    return {
        "needs_kb": needs_kb,
        "rewrite": rewrite,
        "run_probe": run_probe,
        "grade": grade,
        "deep_retrieve": deep_retrieve,
    }
