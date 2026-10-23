import pytest

from app.schemas.extracted_document import Block, ExtractedDocument, Section
from app.services.chunking import NoChunkerError, WebChunker, chunker_for, estimate_tokens
from app.services.chunking.web import render_block, split_sentences


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
    sizes = {"target_tokens": 30, "max_tokens": 60, "min_tokens": 8, "overlap_tokens": 0}
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
    assert (found.name, found.version) == ("web", 2)


def test_a_mime_type_without_a_strategy_raises() -> None:
    with pytest.raises(NoChunkerError):
        chunker_for("application/pdf")


def sentence_block(sentences: list[str]) -> Block:
    return Block(type="paragraph", text=" ".join(sentences))


def test_a_split_section_overlaps_with_the_trailing_block_of_the_previous_piece() -> None:
    first, second, third = para(12, "aa"), para(12, "bb"), para(12, "cc")
    doc = make_doc((["Big"], [first, second, third]))

    chunks = chunker(target_tokens=20, overlap_tokens=12).chunk(doc)

    assert [c.content for c in chunks] == [
        first.text,
        f"{first.text}\n\n{second.text}",
        f"{second.text}\n\n{third.text}",
    ]
    # ranges cover each piece's own blocks, not the repeated tail
    assert [(c.block_start, c.block_end) for c in chunks] == [(0, 1), (1, 2), (2, 3)]


def test_overlap_falls_back_to_trailing_sentences_when_the_last_block_is_big() -> None:
    long_block = sentence_block(["One two three.", "Four five six.", "Seven eight nine."])
    doc = make_doc((["Big"], [long_block, para(15, "next")]))

    chunks = chunker(target_tokens=12, max_tokens=40, overlap_tokens=6).chunk(doc)

    # all 9 words would not fit in 6, so only the trailing sentences that fit are repeated
    assert chunks[1].content.startswith("Four five six. Seven eight nine.")
    assert "One two three." not in chunks[1].content


def test_no_overlap_when_not_even_one_sentence_fits() -> None:
    doc = make_doc((["Big"], [para(15, "aa"), para(15, "bb")]))

    chunks = chunker(target_tokens=20, overlap_tokens=5).chunk(doc)

    assert chunks[1].content == para(15, "bb").text


def test_no_overlap_between_sections_or_merged_chunks() -> None:
    doc = make_doc(
        (["A"], [heading("A"), para(20, "aa")]),
        (["B"], [heading("B"), para(20, "bb")]),
    )

    chunks = chunker(target_tokens=25, overlap_tokens=20).chunk(doc)

    assert [c.heading_path for c in chunks] == [["A"], ["B"]]
    assert "aa" not in chunks[1].content


def test_overlap_counts_toward_the_chunk_size() -> None:
    doc = make_doc((["Big"], [para(14, f"w{i}") for i in range(6)]))

    chunks = chunker(target_tokens=30, max_tokens=60, overlap_tokens=14).chunk(doc)

    assert len(chunks) > 1
    assert all(c.token_count <= 30 for c in chunks)


def test_an_oversized_paragraph_is_split_on_sentences() -> None:
    sentences = [f"Sentence number {i} is here." for i in range(20)]
    doc = make_doc((["X"], [sentence_block(sentences)]))

    chunks = chunker().chunk(doc)

    assert len(chunks) > 1
    assert all(c.token_count <= 60 for c in chunks)
    assert all(c.content.endswith(".") for c in chunks)
    assert " ".join(c.content for c in chunks) == " ".join(sentences)


def test_an_oversized_list_is_split_on_whole_items() -> None:
    items = [f"item {i} with a few words" for i in range(30)]
    doc = make_doc((["X"], [Block(type="list", items=items)]))

    chunks = chunker().chunk(doc)

    assert len(chunks) > 1
    assert all(c.token_count <= 60 for c in chunks)
    lines = [line for c in chunks for line in c.content.splitlines()]
    assert lines == [f"- {item}" for item in items]


def test_an_oversized_table_repeats_its_header_row() -> None:
    rows = [["name", "value"]] + [[f"row{i}", "v v v"] for i in range(40)]
    doc = make_doc((["X"], [Block(type="table", rows=rows)]))

    chunks = chunker().chunk(doc)

    assert len(chunks) > 1
    assert all(c.content.splitlines()[0] == "name | value" for c in chunks)
    assert all(c.token_count <= 60 for c in chunks)
    body = [line for c in chunks for line in c.content.splitlines() if line != "name | value"]
    assert body == [f"row{i} | v v v" for i in range(40)]


def test_oversized_code_is_split_on_lines_and_every_piece_is_fenced() -> None:
    lines = [f"x{i} = {i} + 1 + 2 + 3" for i in range(60)]
    doc = make_doc((["X"], [Block(type="code", text="\n".join(lines))]))

    chunks = chunker().chunk(doc)

    assert len(chunks) > 1
    assert all(c.token_count <= 60 for c in chunks)
    for chunk in chunks:
        assert chunk.content.startswith("```\n") and chunk.content.endswith("\n```")
    body = [ln for c in chunks for ln in c.content.splitlines() if ln != "```"]
    assert body == lines


def test_text_without_any_break_is_cut_to_fit_as_a_last_resort() -> None:
    doc = make_doc((["X"], [Block(type="paragraph", text="x" * 2000)]))

    chunks = WebChunker(target_tokens=100, max_tokens=200, min_tokens=10).chunk(doc)

    assert all(c.token_count <= 200 for c in chunks)
    assert "".join(c.content for c in chunks) == "x" * 2000


def test_a_hard_cut_prefers_whitespace() -> None:
    text = " ".join(["word"] * 400)
    doc = make_doc((["X"], [Block(type="paragraph", text=text)]))

    chunks = WebChunker(target_tokens=100, max_tokens=200, min_tokens=10).chunk(doc)

    assert len(chunks) > 1
    assert all(chunk.content.split() == ["word"] * len(chunk.content.split()) for chunk in chunks)


def test_every_chunk_stays_within_max_tokens_with_overlap_on() -> None:
    doc = make_doc(
        (["A"], [heading("A"), para(120, "aa"), Block(type="list", items=["i " * 5] * 40)]),
        (["B"], [heading("B"), sentence_block(["Some words go here."] * 30)]),
    )

    chunks = chunker(overlap_tokens=10).chunk(doc)

    assert all(c.token_count <= 60 for c in chunks)


def test_sentence_splitter_keeps_punctuation_and_ignores_decimals() -> None:
    assert split_sentences("Pi is 3.14 today. The end! 9 lives? Done.") == [
        "Pi is 3.14 today.",
        "The end!",
        "9 lives?",
        "Done.",
    ]
    assert split_sentences("one. two") == ["one. two"]  # lowercase after the period: no split
    assert split_sentences("") == []


def test_a_tiny_leading_chunk_leads_the_next_large_section() -> None:
    # nav text before the title is under min_tokens and the section after it is over target
    doc = make_doc(
        ([], [Block(type="paragraph", text="Home / Security")]),
        (["Title"], [heading("Title"), para(28), para(28)]),
    )

    chunks = chunker().chunk(doc)

    assert chunks[0].content.startswith("Home / Security\n\n# Title")
    assert chunks[0].heading_path == ["Title"]
    assert chunks[0].block_start == 0
    assert all(c.token_count > 3 for c in chunks)


def test_a_tiny_chunk_grows_to_the_cap_instead_of_standing_alone() -> None:
    doc = make_doc(
        (["A"], [heading("A"), para(3)]),
        (["B"], [heading("B"), para(29)]),
    )

    chunks = chunker().chunk(doc)

    assert len(chunks) == 1  # 4 + 30 words is over target (30) but under max (60)


def test_a_small_first_piece_takes_the_next_block_rather_than_being_repeated() -> None:
    doc = make_doc(
        (["T"], [heading("T"), para(5, "first"), para(28), para(28)]),
    )

    chunks = chunker(overlap_tokens=10).chunk(doc)

    first_block = words(5, "first")
    assert chunks[0].content.count(first_block) == 1
    assert sum(c.content.count(first_block) for c in chunks) == 1  # not copied as overlap
    assert all(c.token_count <= 60 for c in chunks)
