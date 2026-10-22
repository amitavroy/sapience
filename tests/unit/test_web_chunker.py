import pytest

from app.schemas.extracted_document import Block, ExtractedDocument, Section
from app.services.chunking import NoChunkerError, WebChunker, chunker_for, estimate_tokens
from app.services.chunking.web import render_block


def words(n: int, word: str = "w") -> str:
    return " ".join([word] * n)


def para(n: int, word: str = "w") -> Block:
    return Block(type="paragraph", text=words(n, word))


def heading(text: str, level: int = 1) -> Block:
    return Block(type="heading", text=text, level=level)


def make_doc(*sections: tuple[list[str], list[Block]]) -> ExtractedDocument:
    """Build a document from (heading_path, blocks) pairs; sections follow in order."""
    blocks: list[Block] = []
    spans: list[Section] = []
    for path, section_blocks in sections:
        spans.append(
            Section(heading_path=path, start=len(blocks), end=len(blocks) + len(section_blocks))
        )
        blocks.extend(section_blocks)
    return ExtractedDocument(
        source_uri="https://a.test/p",
        title="Page",
        mime_type="text/html",
        content_hash="hash",
        blocks=blocks,
        sections=spans,
    )


def chunker(**kwargs) -> WebChunker:
    """Sizes in words, so assertions are easy to reason about."""
    sizes = {"target_tokens": 30, "max_tokens": 60, "min_tokens": 8}
    return WebChunker(count_tokens=lambda text: len(text.split()), **{**sizes, **kwargs})


def test_small_sibling_sections_merge_with_their_common_prefix() -> None:
    doc = make_doc(
        (["Guide", "Install"], [heading("Install", 2), para(5)]),
        (["Guide", "Run"], [heading("Run", 2), para(5)]),
    )

    [only] = chunker().chunk(doc)

    assert only.heading_path == ["Guide"]
    assert only.content.startswith("## Install")
    assert "## Run" in only.content


def test_sections_in_different_branches_are_not_merged() -> None:
    doc = make_doc(
        (["A"], [heading("A"), para(15)]),
        (["B"], [heading("B"), para(5)]),
    )

    chunks = chunker().chunk(doc)

    assert [c.heading_path for c in chunks] == [["A"], ["B"]]


def test_a_chunk_under_min_tokens_merges_forward_across_branches() -> None:
    doc = make_doc(
        (["A"], [heading("A")]),  # 2 words: under min_tokens
        (["B"], [heading("B"), para(5)]),
    )

    [only] = chunker().chunk(doc)

    assert only.heading_path == []  # nothing in common
    assert "# A" in only.content and "# B" in only.content


def test_content_before_the_first_heading_merges_forward_when_small() -> None:
    doc = make_doc(([], [para(3)]), (["A"], [heading("A"), para(5)]))

    [only] = chunker().chunk(doc)

    assert only.block_start == 0
    assert only.content.startswith("w w w")


def test_a_large_section_is_split_at_block_boundaries() -> None:
    doc = make_doc((["Big"], [heading("Big"), para(20), para(20), para(20)]))

    chunks = chunker().chunk(doc)

    assert len(chunks) == 3
    assert chunks[0].content.startswith("# Big")
    assert all(c.heading_path == ["Big"] for c in chunks)
    # the heading stays with the first block after it
    assert (chunks[0].block_start, chunks[0].block_end) == (0, 2)
    assert (chunks[1].block_start, chunks[1].block_end) == (2, 3)


def test_a_tiny_last_piece_is_folded_into_the_previous_one() -> None:
    doc = make_doc((["Big"], [para(25), para(25), para(3)]))

    chunks = chunker().chunk(doc)

    assert [(c.block_start, c.block_end) for c in chunks] == [(0, 1), (1, 3)]


def test_no_text_is_lost_and_order_is_kept() -> None:
    doc = make_doc(
        ([], [para(4, "intro")]),
        (["A"], [heading("A"), para(40, "alpha"), para(40, "beta")]),
        (["B"], [heading("B"), para(5, "gamma")]),
        (["B", "C"], [heading("C", 2), para(5, "delta")]),
    )

    chunks = chunker().chunk(doc)
    joined = "\n".join(c.content for c in chunks)

    positions = [joined.index(word) for word in ("intro", "alpha", "beta", "gamma", "delta")]
    assert positions == sorted(positions)
    for block in doc.blocks:
        assert block.text in joined


def test_block_ranges_are_contiguous_and_cover_every_block() -> None:
    doc = make_doc(
        ([], [para(4)]),
        (["A"], [heading("A"), para(40), para(40)]),
        (["B"], [heading("B"), para(5)]),
    )

    chunks = chunker().chunk(doc)

    assert chunks[0].block_start == 0
    assert chunks[-1].block_end == len(doc.blocks)
    for previous, following in zip(chunks, chunks[1:], strict=False):
        assert previous.block_end == following.block_start


def test_token_count_matches_the_content() -> None:
    doc = make_doc((["A"], [heading("A"), para(7)]))

    [only] = chunker().chunk(doc)

    assert only.token_count == len(only.content.split())


def test_output_is_deterministic() -> None:
    doc = make_doc((["A"], [heading("A"), para(40), para(40)]), (["B"], [para(5)]))

    assert chunker().chunk(doc) == chunker().chunk(doc)


def test_a_document_without_sections_is_one_section() -> None:
    doc = ExtractedDocument(
        source_uri="u", title="t", mime_type="text/html", content_hash="h", blocks=[para(5)]
    )

    [only] = chunker().chunk(doc)

    assert only.heading_path == []


def test_empty_blocks_produce_no_chunks() -> None:
    doc = make_doc(([], [Block(type="paragraph", text="  ")]))

    assert chunker().chunk(doc) == []


def test_blocks_render_as_lightly_marked_text() -> None:
    assert render_block(heading("Title", 3)) == "### Title"
    assert render_block(Block(type="paragraph", text="Plain")) == "Plain"
    assert render_block(Block(type="quote", text="one\ntwo")) == "> one\n> two"
    assert render_block(Block(type="list", items=["a", "  b"])) == "- a\n  - b"
    assert render_block(Block(type="table", rows=[["h1", "h2"], ["x", "y"]])) == "h1 | h2\nx | y"
    assert render_block(Block(type="code", text="print(1)")) == "```\nprint(1)\n```"


def test_estimate_tokens_is_characters_divided_by_four_rounded_up() -> None:
    assert estimate_tokens("") == 0
    assert estimate_tokens("abcd") == 1
    assert estimate_tokens("abcde") == 2


@pytest.mark.parametrize("mime_type", ["text/html", "application/xhtml+xml"])
def test_html_mime_types_use_the_web_chunker(mime_type: str) -> None:
    found = chunker_for(mime_type)

    assert isinstance(found, WebChunker)
    assert (found.name, found.version) == ("web", 1)


def test_a_mime_type_without_a_strategy_raises() -> None:
    with pytest.raises(NoChunkerError):
        chunker_for("application/pdf")
