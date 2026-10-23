from typing import Literal

import httpx
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from app.core.config import settings

Role = Literal["chat", "summary"]


class ConversationError(Exception):
    pass


def get_model(role: Role) -> BaseChatModel:
    model = settings.llm_summary_model if role == "summary" else ""
    model = model or settings.llm_chat_model
    if not settings.llm_api_key or not model:
        raise ConversationError("LLM_API_KEY / LLM_CHAT_MODEL are not set")
    return ChatOpenAI(
        model=model,
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        # An httpx.Timeout is unhashable, so langchain_openai builds a client for this model
        # instead of reusing its process-wide cached one. That cached client is bound to the
        # event loop that first used it, and every Celery task runs in its own loop.
        timeout=httpx.Timeout(settings.llm_timeout_seconds),
        max_retries=0,  # the drain owns retries
    )
