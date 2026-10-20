from collections.abc import Callable
from pathlib import Path

import httpx
import pytest

from app.core.config import settings
from app.services import web_extractor
from app.services.web_extractor import ExtractionError, ExtractionErrorReason

PAGES = Path(__file__).parent.parent / "fixtures" / "pages"
HTML = {"content-type": "text/html; charset=utf-8"}


def page_bytes(name: str) -> bytes:
    return (PAGES / name).read_bytes()


async def extract_from(
    handler: Callable[[httpx.Request], httpx.Response], url: str = "https://a.test/p"
):
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        return await web_extractor.extract_url(client, url)


async def extract_fixture(name: str, headers: dict | None = None):
    body = page_bytes(name)
    return await extract_from(lambda _: httpx.Response(200, content=body, headers=headers or HTML))


async def test_scripts_styles_and_hidden_content_never_reach_the_output() -> None:
    doc = await extract_fixture("with_scripts.html")

    assert [b.text for b in doc.blocks] == ["Visible before", "Visible after"]
    for leaked in (
        "HEAD_SCRIPT",
        "BODY_SCRIPT",
        "STYLE_TEXT",
        "COMMENT_TEXT",
        "NOSCRIPT_TEXT",
        "ARIA_HIDDEN_TEXT",
        "HIDDEN_ATTR_TEXT",
        "OPTION_TEXT",
        "BUTTON_TEXT",
    ):
        assert leaked not in doc.text()
    assert doc.title == "Scripts page"
    assert doc.metadata["language"] == "en"


async def test_plain_markup_without_paragraphs_is_kept_in_order() -> None:
    doc = await extract_fixture("plain_markup.html")

    assert [(b.type, b.text) for b in doc.blocks] == [
        ("paragraph", "First line second line"),
        ("paragraph", "Loose span text"),
        ("paragraph", "Last boldtext"),
    ]


@pytest.mark.parametrize("name", ["javascript_app.html", "empty_body.html"])
async def test_page_without_content_raises_empty_content(name: str) -> None:
    with pytest.raises(ExtractionError) as exc:
        await extract_fixture(name)

    assert exc.value.reason is ExtractionErrorReason.EMPTY_CONTENT


async def test_charset_declared_only_in_meta_is_decoded() -> None:
    doc = await extract_fixture("latin1_meta_charset.html", headers={"content-type": "text/html"})

    assert doc.blocks[0].text == "Café crème brûlée"
    assert doc.title == "Café"


async def test_redirect_sets_source_uri_to_the_final_url() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/old":
            return httpx.Response(301, headers={"location": "https://a.test/new"})
        return httpx.Response(200, content=b"<p>hi</p>", headers=HTML)

    doc = await extract_from(handler, "https://a.test/old")

    assert doc.requested_url == "https://a.test/old"
    assert doc.source_uri == "https://a.test/new"
    assert doc.status_code == 200
    assert doc.mime_type == "text/html"
    assert len(doc.content_hash) == 64


async def test_request_sends_the_configured_user_agent() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, content=b"<p>hi</p>", headers=HTML)

    await extract_from(handler)

    assert seen[0].headers["user-agent"] == settings.crawler_user_agent


async def test_declared_content_length_over_the_cap_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "crawler_max_bytes", 10)

    with pytest.raises(ExtractionError) as exc:
        await extract_from(
            lambda _: httpx.Response(
                200, content=b"<p>hi</p>", headers={**HTML, "content-length": "999"}
            )
        )

    assert exc.value.reason is ExtractionErrorReason.TOO_LARGE


async def test_streamed_body_over_the_cap_is_rejected_without_content_length(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "crawler_max_bytes", 10)

    async def body():
        yield b"<p>" + b"x" * 20
        yield b"</p>"

    with pytest.raises(ExtractionError) as exc:
        await extract_from(lambda _: httpx.Response(200, content=body(), headers=HTML))

    assert exc.value.reason is ExtractionErrorReason.TOO_LARGE


async def test_non_html_content_type_is_rejected() -> None:
    with pytest.raises(ExtractionError) as exc:
        await extract_from(
            lambda _: httpx.Response(
                200, content=b"%PDF", headers={"content-type": "application/pdf"}
            )
        )

    assert exc.value.reason is ExtractionErrorReason.NOT_HTML


async def test_missing_content_type_is_sniffed_from_the_body() -> None:
    html = await extract_from(lambda _: httpx.Response(200, content=b"\n <!DOCTYPE html><p>hi</p>"))
    assert html.mime_type == "text/html"

    with pytest.raises(ExtractionError) as exc:
        await extract_from(lambda _: httpx.Response(200, content=b'{"a": 1}'))
    assert exc.value.reason is ExtractionErrorReason.NOT_HTML


async def test_non_http_scheme_is_rejected() -> None:
    with pytest.raises(ExtractionError) as exc:
        await extract_from(lambda _: httpx.Response(200), "ftp://a.test/file")

    assert exc.value.reason is ExtractionErrorReason.INVALID_URL


async def test_error_status_is_never_extracted_as_content() -> None:
    with pytest.raises(ExtractionError) as exc:
        await extract_from(lambda _: httpx.Response(404, content=b"<p>not found</p>", headers=HTML))

    assert exc.value.reason is ExtractionErrorReason.HTTP_STATUS
    assert exc.value.status_code == 404


@pytest.mark.parametrize(("status", "retryable"), [(500, True), (404, False), (503, False)])
async def test_only_a_500_is_marked_retryable(status: int, retryable: bool) -> None:
    with pytest.raises(ExtractionError) as exc:
        await extract_from(lambda _: httpx.Response(status))

    assert exc.value.reason is ExtractionErrorReason.HTTP_STATUS
    assert exc.value.status_code == status
    assert exc.value.retryable is retryable


@pytest.mark.parametrize("error", [httpx.ConnectTimeout, httpx.ReadTimeout, httpx.ConnectError])
async def test_timeouts_and_connection_errors_are_retryable_network_errors(error: type) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise error("boom", request=request)

    with pytest.raises(ExtractionError) as exc:
        await extract_from(handler)

    assert exc.value.reason is ExtractionErrorReason.NETWORK
    assert exc.value.retryable is True


async def test_structured_page_has_typed_blocks_in_order() -> None:
    doc = await extract_fixture("structured.html")

    assert [(b.type, b.level) for b in doc.blocks] == [
        ("heading", 1),
        ("paragraph", None),
        ("heading", 2),
        ("list", None),
        ("heading", 2),
        ("table", None),
        ("heading", 3),
        ("code", None),
        ("quote", None),
        ("paragraph", None),
    ]
    by_type = {b.type: b for b in reversed(doc.blocks)}
    assert by_type["list"].items == ["First", "  Nested one", "  Nested two", "Second"]
    assert by_type["table"].rows == [["Name", "Value"], ["alpha", "1"], ["beta", "2"]]
    assert by_type["code"].text == "def f():\n    return 1\n"  # whitespace kept exactly
    assert by_type["quote"].text == "Quoted words."
    assert doc.blocks[-1].text == "Figure caption."  # figcaption kept, alt text dropped
    assert "ALT_TEXT" not in doc.text()


async def test_structured_page_metadata_comes_from_the_head_only() -> None:
    doc = await extract_fixture("structured.html")

    assert doc.title == "Structured page"
    assert doc.metadata == {
        "description": "A page with every block type",
        "language": "en-GB",
        "canonical_url": "https://example.test/structured",
        "og": {"og:title": "OG structured", "og:type": "article"},
    }
    assert "Structured page" not in doc.text()


async def test_sections_are_index_ranges_with_a_heading_path() -> None:
    doc = await extract_fixture("structured.html")

    assert [(s.heading_path, s.start, s.end) for s in doc.sections] == [
        (["Guide"], 0, 2),
        (["Guide", "Steps"], 2, 4),
        (["Guide", "Data"], 4, 6),
        (["Guide", "Data", "Code"], 6, 10),
    ]
    code_section = doc.sections[3]
    assert [b.type for b in doc.section_blocks(code_section)] == [
        "heading",
        "code",
        "quote",
        "paragraph",
    ]


async def test_nested_blocks_lose_no_text_and_duplicate_none() -> None:
    doc = await extract_fixture("nested_blocks.html")

    assert [(b.type, b.text or b.items) for b in doc.blocks] == [
        ("paragraph", "Text before the first heading."),
        ("heading", "Top"),
        ("list", ["Paragraph inside item", "Plain item"]),
        ("quote", "Quoted paragraph and trailing quote text"),
        ("paragraph", "Loose text"),
        ("paragraph", "Paragraph beside it"),
        ("paragraph", "more loose text"),
        ("heading", "Skipped level"),
        ("paragraph", "Under h3."),
        ("heading", "Back up"),
        ("paragraph", "Under h2."),
        ("heading", "Second top"),
        ("paragraph", "Fresh start."),
    ]
    text = doc.text()
    for phrase in ("Paragraph inside item", "Quoted paragraph", "Paragraph beside it"):
        assert text.count(phrase) == 1


async def test_content_before_the_first_heading_is_its_own_section() -> None:
    doc = await extract_fixture("nested_blocks.html")

    assert (doc.sections[0].heading_path, doc.sections[0].start, doc.sections[0].end) == ([], 0, 1)


async def test_skipped_heading_levels_nest_and_a_second_h1_resets_the_path() -> None:
    doc = await extract_fixture("nested_blocks.html")

    assert [s.heading_path for s in doc.sections] == [
        [],
        ["Top"],
        ["Top", "Skipped level"],
        ["Top", "Back up"],
        ["Second top"],
    ]


@pytest.mark.parametrize(
    ("html", "title"),
    [
        (b"<title>From title</title><h1>H</h1><p>x</p>", "From title"),
        (b'<meta property="og:title" content="From og"><h1>H</h1><p>x</p>', "From og"),
        (b"<h1>From h1</h1><p>x</p>", "From h1"),
        (b"<p>x</p>", "https://a.test/p"),
    ],
    ids=["title", "og", "h1", "source_uri"],
)
async def test_title_falls_back_through_og_h1_and_the_url(html: bytes, title: str) -> None:
    doc = await extract_from(lambda _: httpx.Response(200, content=html, headers=HTML))

    assert doc.title == title


async def extract_html(html: str, url: str = "https://a.test/dir/page"):
    return await extract_from(
        lambda _: httpx.Response(200, content=html.encode(), headers=HTML), url
    )


async def test_relative_links_resolve_against_the_page_url() -> None:
    doc = await extract_html(
        '<a href="next">Next</a> <a href="/root">Root</a> <a href="../up">Up</a>'
    )

    assert [link.href for link in doc.links] == [
        "https://a.test/dir/next",
        "https://a.test/root",
        "https://a.test/up",
    ]
    assert [link.text for link in doc.links] == ["Next", "Root", "Up"]


async def test_base_href_wins_over_the_page_url() -> None:
    doc = await extract_html(
        '<head><base href="https://cdn.test/docs/"></head><a href="intro">Intro</a>'
    )

    assert [link.href for link in doc.links] == ["https://cdn.test/docs/intro"]


async def test_only_http_links_are_kept_and_fragments_are_stripped() -> None:
    doc = await extract_html(
        """
        <a href="mailto:a@b.test">mail</a> <a href="tel:123">tel</a>
        <a href="javascript:void(0)">js</a> <a href="data:text/plain,x">data</a>
        <a href="#top">top</a> <a href="">empty</a> <a>no href</a>
        <a href="/page#section">kept</a>
        """
    )

    assert [link.href for link in doc.links] == ["https://a.test/page"]


async def test_duplicate_links_are_merged_keeping_the_first_non_empty_text() -> None:
    doc = await extract_html(
        '<a href="/x"></a> <a href="/x#one">First text</a> <a href="/x">Second text</a>'
    )

    [link] = doc.links
    assert (link.href, link.text) == ("https://a.test/x", "First text")


async def test_www_counts_as_internal_but_other_subdomains_do_not() -> None:
    doc = await extract_html(
        """
        <a href="https://www.a.test/w">www</a> <a href="https://A.TEST/u">upper</a>
        <a href="https://blog.a.test/b">blog</a> <a href="https://other.test/o">other</a>
        """
    )

    assert {link.text: link.internal for link in doc.links} == {
        "www": True,
        "upper": True,
        "blog": False,
        "other": False,
    }


async def test_links_in_removed_content_are_not_collected() -> None:
    doc = await extract_html(
        """
        <a href="/kept">kept</a>
        <div hidden><a href="/hidden">hidden</a></div>
        <div aria-hidden="true"><a href="/aria">aria</a></div>
        <noscript><a href="/noscript">noscript</a></noscript>
        <script>var s = '<a href="/script">x</a>';</script>
        """
    )

    assert [link.href for link in doc.links] == ["https://a.test/kept"]


async def test_hash_is_stable_across_markup_changes() -> None:
    plain = await extract_html("<h1>Title</h1><p>Hello   world</p>")
    marked_up = await extract_html(
        "<body><div><h1 class='x'>Title</h1></div>"
        "<section><p>Hello <b>world</b></p></section></body>"
    )

    assert plain.content_hash == marked_up.content_hash
    assert len(plain.content_hash) == 64
    assert int(plain.content_hash, 16) >= 0  # hex


async def test_hash_changes_with_a_one_word_change() -> None:
    before = await extract_html("<p>Hello world</p>")
    after = await extract_html("<p>Hello there</p>")

    assert before.content_hash != after.content_hash


async def test_hash_ignores_title_and_metadata() -> None:
    one = await extract_html("<title>One</title><meta name=description content=a><p>Same</p>")
    two = await extract_html("<title>Two</title><meta name=description content=b><p>Same</p>")

    assert one.content_hash == two.content_hash
