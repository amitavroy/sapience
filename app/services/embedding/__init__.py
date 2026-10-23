from app.core.config import settings
from app.db.types import EMBEDDING_DIM
from app.models.chunk import Chunk
from app.services.embedding.base import Embedder, EmbeddingError, EmbedResult
from app.services.embedding.openai_compatible import OpenAICompatibleEmbedder

__all__ = [
    "Embedder",
    "EmbedResult",
    "EmbeddingError",
    "embedding_input",
    "get_embedder",
]

_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def get_embedder() -> Embedder:
    """By settings.embedding_provider: "openrouter" or "openai"."""
    default_url = _OPENROUTER_BASE_URL if settings.embedding_provider == "openrouter" else None
    embedder = OpenAICompatibleEmbedder(
        provider=settings.embedding_provider,
        model=settings.embedding_model,
        dimensions=EMBEDDING_DIM,
        api_key=settings.embedding_api_key,
        base_url=settings.embedding_base_url or default_url,
        timeout=settings.embedding_timeout_seconds,
    )
    if embedder.dimensions != EMBEDDING_DIM:
        raise EmbeddingError(
            f"embedder gives {embedder.dimensions} dimensions, need {EMBEDDING_DIM}"
        )
    return embedder


def embedding_input(title: str | None, chunk: Chunk) -> str:
    """Title and heading breadcrumb plus content: the breadcrumb goes into the vector only."""
    heading_path = (chunk.meta or {}).get("heading_path") or []
    lines = [title or ""]
    if heading_path:
        lines.append(" > ".join(heading_path))
    return "\n".join(lines) + "\n\n" + chunk.content
