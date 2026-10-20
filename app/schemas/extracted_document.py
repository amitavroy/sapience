from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

BlockType = Literal["paragraph"]  # slice 4 adds heading, list, table, code, quote


class Block(BaseModel):
    type: BlockType
    text: str = ""


class ExtractedDocument(BaseModel):
    source_uri: str  # final URL after redirects
    title: str
    mime_type: str  # no parameters, e.g. "text/html"
    content_hash: str  # sha256 of normalised text(), maps to Document.content_hash
    requested_url: str | None = None
    status_code: int | None = None
    fetched_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)  # description, language, canonical_url
    blocks: list[Block]

    def text(self) -> str:
        return "\n\n".join(block.text for block in self.blocks)
