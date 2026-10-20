from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

BlockType = Literal["heading", "paragraph", "list", "table", "code", "quote"]


class Block(BaseModel):
    type: BlockType
    text: str = ""  # heading, paragraph, code, quote
    level: int | None = None  # heading only
    items: list[str] = Field(default_factory=list)  # list only; nested items are indented
    rows: list[list[str]] = Field(default_factory=list)  # table only

    def text_form(self) -> str:
        """The block as it contributes to ExtractedDocument.text() (and so to the hash)."""
        if self.type == "list":
            return "\n".join(f"- {item}" for item in self.items)
        if self.type == "table":
            return "\n".join(" | ".join(row) for row in self.rows)
        return self.text


class Section(BaseModel):
    heading_path: list[str]  # [] for content before the first heading
    start: int  # blocks[start:end]; blocks[start] is the heading when there is one
    end: int


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
    sections: list[Section] = Field(default_factory=list)

    def text(self) -> str:
        return "\n\n".join(block.text_form() for block in self.blocks)

    def section_blocks(self, section: Section) -> list[Block]:
        return self.blocks[section.start : section.end]
