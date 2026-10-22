from app.services.chunking.base import ChunkDraft, Chunker
from app.services.chunking.tokens import estimate_tokens
from app.services.chunking.web import WebChunker

__all__ = ["Chunker", "ChunkDraft", "NoChunkerError", "chunker_for", "estimate_tokens"]


class NoChunkerError(Exception):
    pass


# MIME type -> strategy. Add `application/pdf` -> PdfChunker here when PDFs arrive.
_CHUNKERS: dict[str, Chunker] = {
    "text/html": WebChunker(),
    "application/xhtml+xml": WebChunker(),
}


def chunker_for(mime_type: str) -> Chunker:
    """Raises NoChunkerError for a MIME type with no strategy."""
    try:
        return _CHUNKERS[mime_type]
    except KeyError:
        raise NoChunkerError(mime_type) from None
