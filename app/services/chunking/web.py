import os.path
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from app.schemas.extracted_document import Block, ExtractedDocument
from app.services.chunking.base import ChunkDraft
from app.services.chunking.tokens import estimate_tokens

# ". The", "? 3", '! "Quote': a sentence end, whitespace, then something that starts a sentence.
# Plain regex, no NLP dependency; abbreviations ("e.g. The") may split early.
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(\[])")


def split_sentences(text: str) -> list[str]:
    return [part for part in _SENTENCE_END.split(text) if part]


def render_block(block: Block) -> str:
    """A block as lightly marked plain text, so structure survives in the chunk."""
    match block.type:
        case "heading":
            return f"{'#' * min(max(block.level or 1, 1), 6)} {block.text}"
        case "quote":
            return "\n".join(f"> {line}" for line in block.text.splitlines())
        case "list":
            lines = []
            for item in block.items:
                body = item.lstrip()
                lines.append(f"{item[: len(item) - len(body)]}- {body}")
            return "\n".join(lines)
        case "table":
            return "\n".join(" | ".join(row) for row in block.rows)
        case "code":
            return f"```\n{block.text}\n```"
        case _:
            return block.text


@dataclass(frozen=True)
class _Piece:
    """One rendered, non-empty block with its index in ExtractedDocument.blocks."""

    index: int
    text: str
    tokens: int
    heading: bool = False


@dataclass(frozen=True)
class _Unit:
    """The pieces of one section."""

    heading_path: list[str]
    pieces: list[_Piece]

    @property
    def tokens(self) -> int:
        return sum(p.tokens for p in self.pieces)


@dataclass(frozen=True)
class WebChunker:
    """Heading-aware chunks for HTML pages.

    Small neighbouring sections are merged; a large section is split at block boundaries.
    Sizes are part of the algorithm: change them together with `version`.
    """

    name: str = "web"
    version: int = 1
    target_tokens: int = 400
    max_tokens: int = 800
    min_tokens: int = 100
    overlap_tokens: int = 60
    count_tokens: Callable[[str], int] = estimate_tokens

    def chunk(self, doc: ExtractedDocument) -> list[ChunkDraft]:
        drafts: list[ChunkDraft] = []
        current: list[_Unit] = []

        def flush() -> None:
            if current:
                drafts.append(self._merged(current))
                current.clear()

        for unit in self._units(doc):
            if unit.tokens > self.target_tokens:
                flush()
                drafts.extend(self._split(unit))
            elif current and self._fits(current, unit):
                current.append(unit)
            else:
                flush()
                current.append(unit)
        flush()
        return drafts

    def _units(self, doc: ExtractedDocument) -> list[_Unit]:
        sections = [(s.heading_path, s.start, s.end) for s in doc.sections]
        if not sections:  # no structure at all: the whole page is one section
            sections = [([], 0, len(doc.blocks))]
        units = []
        for heading_path, start, end in sections:
            pieces = []
            for index in range(start, end):
                block = doc.blocks[index]
                text = render_block(block)
                if not text.strip():
                    continue
                tokens = self.count_tokens(text)
                texts = self._split_block(block, text) if tokens > self.max_tokens else [text]
                for part in texts:
                    pieces.append(
                        _Piece(
                            index,
                            part,
                            self.count_tokens(part),
                            heading=block.type == "heading",
                        )
                    )
            if pieces:
                units.append(_Unit(list(heading_path), pieces))
        return units

    def _split_block(self, block: Block, text: str) -> list[str]:
        """Split one block that is over `max_tokens` into rendered pieces that each fit."""
        match block.type:
            case "list":
                pieces = self._pack(
                    block.items, lambda items: render_block(Block(type="list", items=list(items)))
                )
            case "table" if len(block.rows) > 1:
                # the first row is repeated at the top of every piece
                header = block.rows[0]
                pieces = self._pack(
                    block.rows[1:],
                    lambda rows: render_block(Block(type="table", rows=[header, *rows])),
                )
            case "code":
                pieces = self._pack(
                    block.text.split("\n"),
                    lambda lines: render_block(Block(type="code", text="\n".join(lines))),
                )
            case "quote":
                pieces = self._pack(
                    split_sentences(block.text),
                    lambda parts: render_block(Block(type="quote", text=" ".join(parts))),
                )
            case _:
                pieces = self._pack(split_sentences(block.text), " ".join)
        # last resort: one sentence, item, row or line that is still too big
        return [cut for piece in pieces for cut in self._hard_cut(piece)]

    def _pack(self, items: Sequence[str], render: Callable[[Sequence[str]], str]) -> list[str]:
        """Group whole items into rendered pieces of at most `target_tokens` where possible."""
        pieces: list[str] = []
        current: list[str] = []
        for item in items:
            if current and self.count_tokens(render([*current, item])) > self.target_tokens:
                pieces.append(render(current))
                current = []
            current.append(item)
        if current:
            pieces.append(render(current))
        return pieces

    def _hard_cut(self, text: str) -> list[str]:
        """Windows of about `max_tokens * 4` characters, cut back to the last space when there is
        one. The window is shrunk until the counter agrees that the part fits."""
        parts: list[str] = []
        while text:
            cut = len(text)
            if cut > self.max_tokens * 4:
                cut = text.rfind(" ", 0, self.max_tokens * 4)
                cut = self.max_tokens * 4 if cut <= 0 else cut
            part = text[:cut]
            while (tokens := self.count_tokens(part)) > self.max_tokens and len(part) > 1:
                cut = max(1, len(part) * self.max_tokens // tokens)
                space = part.rfind(" ", 0, cut)
                cut = space if space > 0 else cut
                part = text[:cut]
            parts.append(part.rstrip())
            text = text[cut:].lstrip()
        return parts

    def _fits(self, current: list[_Unit], unit: _Unit) -> bool:
        size = sum(u.tokens for u in current)
        if size + unit.tokens > self.target_tokens:
            return False
        same_branch = _branch(current[-1].heading_path) == _branch(unit.heading_path)
        return same_branch or size < self.min_tokens

    def _merged(self, units: list[_Unit]) -> ChunkDraft:
        heading_path = list(units[0].heading_path)
        for unit in units[1:]:
            heading_path = _common_prefix(heading_path, unit.heading_path)
        pieces = [p for u in units for p in u.pieces]
        return self._draft(pieces, heading_path)

    def _split(self, unit: _Unit) -> list[ChunkDraft]:
        """Greedy split at block boundaries; every piece keeps the section's heading path.

        Each piece after the first starts with a tail of the previous piece (overlap), which
        counts toward the piece's size."""
        groups: list[list[_Piece]] = [[]]
        tails = [""]
        size = 0
        for piece in unit.pieces:
            group = groups[-1]
            over = size + piece.tokens > self.target_tokens
            # a heading stays with the block after it, as long as the cap allows
            lone_heading = len(group) == 1 and group[0].heading
            if lone_heading and size + piece.tokens <= self.max_tokens:
                over = False
            if group and over:
                tail = self._overlap_tail(group)
                groups.append([])
                tails.append(tail)
                size = self.count_tokens(tail) if tail else 0
            if not groups[-1] and size + piece.tokens > self.max_tokens:
                # the overlap would push a big first block over the cap: drop the overlap
                tails[-1] = ""
                size = 0
            groups[-1].append(piece)
            size += piece.tokens
        # a tiny tail reads badly on its own: fold it back if the result stays within the cap
        if len(groups) > 1 and sum(p.tokens for p in groups[-1]) < self.min_tokens:
            merged = groups[-2] + groups[-1]
            if self._joined_tokens(merged, tails[-2]) <= self.max_tokens:
                groups[-2:] = [merged]
                tails[-2:] = [tails[-2]]
        return [
            self._draft(group, unit.heading_path, tail)
            for group, tail in zip(groups, tails, strict=True)
        ]

    def _overlap_tail(self, pieces: list[_Piece]) -> str:
        """The end of a piece, to repeat at the start of the next: whole trailing blocks that fit
        in `overlap_tokens`, else the trailing sentences of the last block. Never a cut word."""
        if self.overlap_tokens <= 0 or pieces[-1].heading:  # a lone heading is no context
            return ""
        taken: list[_Piece] = []
        size = 0
        for piece in reversed(pieces):
            if size + piece.tokens > self.overlap_tokens:
                break
            taken.insert(0, piece)
            size += piece.tokens
        if taken:
            return "\n\n".join(p.text for p in taken)
        sentences: list[str] = []
        size = 0
        for sentence in reversed(split_sentences(pieces[-1].text)):
            tokens = self.count_tokens(sentence)
            if size + tokens > self.overlap_tokens:
                break
            sentences.insert(0, sentence)
            size += tokens
        return " ".join(sentences)

    def _draft(self, pieces: list[_Piece], heading_path: list[str], tail: str = "") -> ChunkDraft:
        # block_start/block_end cover the piece's own blocks; the overlap tail is not counted
        content = "\n\n".join(([tail] if tail else []) + [p.text for p in pieces])
        return ChunkDraft(
            content=content,
            token_count=self.count_tokens(content),
            heading_path=list(heading_path),
            block_start=pieces[0].index,
            block_end=pieces[-1].index + 1,
        )

    def _joined_tokens(self, pieces: list[_Piece], tail: str = "") -> int:
        return self.count_tokens("\n\n".join(([tail] if tail else []) + [p.text for p in pieces]))


def _branch(heading_path: list[str]) -> str | None:
    return heading_path[0] if heading_path else None


def _common_prefix(a: list[str], b: list[str]) -> list[str]:
    return os.path.commonprefix([a, b])
