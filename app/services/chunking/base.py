from dataclasses import dataclass
from typing import Protocol

from app.schemas.extracted_document import ExtractedDocument


@dataclass(frozen=True)
class ChunkDraft:
    content: str
    token_count: int
    heading_path: list[str]
    block_start: int  # range into ExtractedDocument.blocks this chunk came from
    block_end: int


class Chunker(Protocol):
    name: str  # "web"
    version: int  # bump when the output for the same input changes

    def chunk(self, doc: ExtractedDocument) -> list[ChunkDraft]: ...
