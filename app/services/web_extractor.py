import asyncio
import codecs
import hashlib
import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from urllib.parse import urldefrag, urljoin, urlsplit

import httpx
from selectolax.lexbor import LexborHTMLParser, LexborNode

from app.core.config import settings
from app.schemas.extracted_document import Block, ExtractedDocument, Link, Section

# only a plain 500 for now; gateway errors (502-504) are the first candidates to add
RETRYABLE_STATUS_CODES = frozenset({500})
ACCEPTED_MIME_TYPES = {"text/html", "application/xhtml+xml"}
HEADERS = {
    "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
HTML_SNIFF_RE = re.compile(rb"\s*<(!doctype\s+html|html)", re.IGNORECASE)
META_CHARSET_RE = re.compile(rb"<meta[^>]+charset\s*=\s*[\"']?\s*([\w.:-]+)", re.IGNORECASE)

# removed together with their contents
NOISE_TAGS = frozenset(
    "script style noscript template iframe svg canvas link meta input select option textarea "
    "button".split()
)
# emitted once, whole, and not recursed into
BLOCK_TAGS = frozenset("h1 h2 h3 h4 h5 h6 p figcaption ul ol table pre blockquote".split())
# page chrome, removed with its contents. header and footer only count as chrome at page level:
# inside article, section or main they are scoped to that content (an article header holds its h1)
CHROME_TAGS = frozenset({"nav", "aside"})
SCOPED_CHROME_TAGS = frozenset({"header", "footer"})
# the same declarations made with ARIA roles on any element
CHROME_ROLES = frozenset({"navigation", "complementary"})
SCOPED_CHROME_ROLES = frozenset({"banner", "contentinfo"})
CONTENT_ROOT_TAGS = frozenset({"article", "section", "main"})
HEADING_LEVELS = {f"h{n}": n for n in range(1, 7)}
LIST_TAGS = frozenset({"ul", "ol"})
INLINE_TAGS = frozenset(
    "a abbr b bdi bdo cite code data dfn em i kbd mark q s samp small span strong sub sup time "
    "u var wbr".split()
)


class ExtractionErrorReason(StrEnum):
    INVALID_URL = "invalid_url"
    HTTP_STATUS = "http_status"
    NETWORK = "network"
    TOO_LARGE = "too_large"
    NOT_HTML = "not_html"
    EMPTY_CONTENT = "empty_content"


class ExtractionError(Exception):
    def __init__(
        self,
        reason: ExtractionErrorReason,
        message: str,
        *,
        status_code: int | None = None,
        retryable: bool = False,
    ):
        super().__init__(message)
        self.reason = reason
        self.status_code = status_code
        self.retryable = retryable


@dataclass(frozen=True)
class FetchedPage:
    requested_url: str
    final_url: str
    status_code: int
    mime_type: str
    body: bytes
    fetched_at: datetime
    header_charset: str | None = None


async def fetch_page(client: httpx.AsyncClient, url: str) -> FetchedPage:
    """One GET: validate the scheme, stream with the size cap, check status and content type."""
    try:
        return await _fetch_page(client, url)
    except httpx.TransportError as exc:  # timeouts, connection errors, protocol errors
        raise ExtractionError(
            ExtractionErrorReason.NETWORK,
            f"{type(exc).__name__} fetching {url}: {exc}",
            retryable=True,
        ) from exc


async def _fetch_page(client: httpx.AsyncClient, url: str) -> FetchedPage:
    if urlsplit(url).scheme not in ("http", "https"):
        raise ExtractionError(ExtractionErrorReason.INVALID_URL, f"unsupported URL: {url}")

    headers = {"User-Agent": settings.crawler_user_agent, **HEADERS}
    max_bytes = settings.crawler_max_bytes
    async with client.stream(
        "GET",
        url,
        headers=headers,
        timeout=settings.crawler_timeout_seconds,
        follow_redirects=True,
    ) as response:
        if response.status_code >= 400:
            raise ExtractionError(
                ExtractionErrorReason.HTTP_STATUS,
                f"HTTP {response.status_code} for {url}",
                status_code=response.status_code,
                retryable=response.status_code in RETRYABLE_STATUS_CODES,
            )

        mime_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
        if mime_type and mime_type not in ACCEPTED_MIME_TYPES:
            raise ExtractionError(ExtractionErrorReason.NOT_HTML, f"not HTML: {mime_type}")

        declared = response.headers.get("content-length", "")
        if declared.isdigit() and int(declared) > max_bytes:
            raise ExtractionError(
                ExtractionErrorReason.TOO_LARGE, f"content-length {declared} over {max_bytes}"
            )

        # counts decompressed bytes, so a small compressed response can't expand past the cap
        body = bytearray()
        async for chunk in response.aiter_bytes():
            body.extend(chunk)
            if len(body) > max_bytes:
                raise ExtractionError(ExtractionErrorReason.TOO_LARGE, f"body over {max_bytes}")

        if not mime_type:
            if not HTML_SNIFF_RE.match(bytes(body[:1024])):
                raise ExtractionError(ExtractionErrorReason.NOT_HTML, "no content type, not HTML")
            mime_type = "text/html"

        return FetchedPage(
            requested_url=url,
            final_url=str(response.url),
            status_code=response.status_code,
            mime_type=mime_type,
            body=bytes(body),
            fetched_at=datetime.now(UTC),
            header_charset=response.charset_encoding,
        )


def _decode(page: FetchedPage) -> str:
    """Header charset, then <meta> in the first 2 KB, then UTF-8 with replacement."""
    candidates = [page.header_charset]
    if match := META_CHARSET_RE.search(page.body[:2048]):
        candidates.append(match.group(1).decode("ascii", errors="ignore"))
    for name in candidates:
        if not name:
            continue
        try:
            codecs.lookup(name)
        except LookupError:
            continue
        return page.body.decode(name, errors="replace")
    return page.body.decode("utf-8", errors="replace")


def _collapse(text: str) -> str:
    return " ".join(text.split())


def _is_skipped(node: LexborNode, in_content: bool = False) -> bool:
    if node.tag in NOISE_TAGS or node.tag in CHROME_TAGS:
        return True
    attrs = node.attributes
    role = (attrs.get("role") or "").strip().lower()
    if role in CHROME_ROLES:
        return True
    if not in_content and (node.tag in SCOPED_CHROME_TAGS or role in SCOPED_CHROME_ROLES):
        return True
    return "hidden" in attrs or attrs.get("aria-hidden") == "true"


def _text_of(node: LexborNode, exclude: frozenset[str] = frozenset()) -> str:
    """Text under node. Non-inline elements and <br> count as a space, so words don't merge."""
    parts: list[str] = []

    def collect(parent: LexborNode) -> None:
        child = parent.child
        while child is not None:
            tag = child.tag
            if tag == "-text":
                parts.append(child.text_content or "")
            elif tag.startswith("-"):  # comments and other non-element nodes
                pass
            elif not _is_skipped(child, in_content=True):
                spaced = tag == "br" or tag not in INLINE_TAGS
                if spaced:
                    parts.append(" ")
                if tag not in exclude:
                    collect(child)
                if spaced:
                    parts.append(" ")
            child = child.next

    collect(node)
    return _collapse("".join(parts))


def _raw_text(node: LexborNode) -> str:
    """Text under node with its whitespace kept (code blocks); <br> is a newline."""
    parts: list[str] = []
    child = node.child
    while child is not None:
        tag = child.tag
        if tag == "-text":
            parts.append(child.text_content or "")
        elif tag == "br":
            parts.append("\n")
        elif not tag.startswith("-") and not _is_skipped(child, in_content=True):
            parts.append(_raw_text(child))
        child = child.next
    return "".join(parts)


def _children(node: LexborNode, tags: frozenset[str]) -> list[LexborNode]:
    found = []
    child = node.child
    while child is not None:
        if child.tag in tags and not _is_skipped(child, in_content=True):
            found.append(child)
        child = child.next
    return found


def _list_items(list_node: LexborNode, depth: int = 0) -> list[str]:
    """Item text per <li>; nested lists are flattened in, indented two spaces per level."""
    items: list[str] = []
    for li in _children(list_node, frozenset({"li"})):
        if text := _text_of(li, exclude=LIST_TAGS):
            items.append("  " * depth + text)
        for nested in _children(li, LIST_TAGS):
            items.extend(_list_items(nested, depth + 1))
    return items


def _table_rows(table: LexborNode) -> list[list[str]]:
    rows: list[list[str]] = []
    trs: list[LexborNode] = []
    for part in _children(table, frozenset({"thead", "tbody", "tfoot", "tr"})):
        trs.extend(_children(part, frozenset({"tr"})) if part.tag != "tr" else [part])
    for tr in trs:
        cells = [_text_of(cell) for cell in _children(tr, frozenset({"th", "td"}))]
        if any(cells):
            rows.append(cells)
    return rows


def _block_elements(node: LexborNode) -> list[Block]:
    """The block(s) for one block element; empty ones are dropped."""
    tag = node.tag
    blocks: list[Block] = []
    if tag in HEADING_LEVELS:
        if text := _text_of(node):
            blocks.append(Block(type="heading", text=text, level=HEADING_LEVELS[tag]))
    elif tag in LIST_TAGS:
        if items := _list_items(node):
            blocks.append(Block(type="list", items=items))
    elif tag == "table":
        for caption in _children(node, frozenset({"caption"})):
            if text := _text_of(caption):
                blocks.append(Block(type="paragraph", text=text))
        if rows := _table_rows(node):
            blocks.append(Block(type="table", rows=rows))
    elif tag == "pre":
        if (text := _raw_text(node)).strip():
            blocks.append(Block(type="code", text=text))
    elif tag == "blockquote":
        if text := _text_of(node):
            blocks.append(Block(type="quote", text=text))
    elif text := _text_of(node):  # p, figcaption
        blocks.append(Block(type="paragraph", text=text))
    return blocks


def _build_sections(blocks: list[Block]) -> list[Section]:
    """A section starts at each heading; heading_path comes from a stack of enclosing headings."""
    sections: list[Section] = []
    stack: list[tuple[int, str]] = []
    start = 0
    path: list[str] = []
    for index, block in enumerate(blocks):
        if block.type != "heading":
            continue
        if index > start:  # close the section before this heading (or the pre-heading content)
            sections.append(Section(heading_path=path, start=start, end=index))
        while stack and stack[-1][0] >= (block.level or 1):
            stack.pop()
        stack.append((block.level or 1, block.text))
        path = [text for _, text in stack]
        start = index
    sections.append(Section(heading_path=path, start=start, end=len(blocks)))
    return sections


def _bare_host(url: str) -> str:
    host = (urlsplit(url).hostname or "").lower()
    return host.removeprefix("www.")


def _extract_links(tree: LexborHTMLParser, source_uri: str) -> list[Link]:
    """Absolute http(s) links from the visible body, fragments stripped, deduped by href."""
    base_node = tree.css_first("head base[href]")
    base = urljoin(source_uri, base_node.attributes["href"] or "") if base_node else source_uri
    source_host = _bare_host(source_uri)
    found: dict[str, Link] = {}

    def visit(parent: LexborNode, in_content: bool) -> None:
        child = parent.child
        while child is not None:
            if not child.tag.startswith("-") and not _is_skipped(child, in_content):
                if child.tag == "a":
                    add(child)
                visit(child, in_content or child.tag in CONTENT_ROOT_TAGS)
            child = child.next

    def add(anchor: LexborNode) -> None:
        raw = (anchor.attributes.get("href") or "").strip()
        if not raw or raw.startswith("#"):
            return
        href, _ = urldefrag(urljoin(base, raw))
        if urlsplit(href).scheme not in ("http", "https"):
            return
        text = _text_of(anchor)
        if existing := found.get(href):
            if not existing.text:
                existing.text = text
            return
        found[href] = Link(href=href, text=text, internal=_bare_host(href) == source_host)

    if tree.body is not None:
        visit(tree.body, in_content=False)
    return list(found.values())


def _walk_blocks(parent: LexborNode, blocks: list[Block], in_content: bool = False) -> None:
    """Block elements are emitted whole; containers are recursed; loose inline text is gathered."""
    loose: list[str] = []

    def flush() -> None:
        if text := _collapse("".join(loose)):
            blocks.append(Block(type="paragraph", text=text))
        loose.clear()

    child = parent.child
    while child is not None:
        tag = child.tag
        if tag == "-text":
            loose.append(child.text_content or "")
        elif tag.startswith("-") or _is_skipped(child, in_content):
            pass
        elif tag in BLOCK_TAGS:
            flush()
            blocks.extend(_block_elements(child))
        elif tag in INLINE_TAGS or tag == "br":
            loose.append(" " if tag == "br" else _text_of(child))
        else:
            flush()
            _walk_blocks(child, blocks, in_content or tag in CONTENT_ROOT_TAGS)
        child = child.next
    flush()


def _metadata(tree: LexborHTMLParser) -> dict:
    def meta(selector: str) -> str:
        node = tree.css_first(selector)
        return _collapse(node.attributes.get("content") or "") if node else ""

    canonical = tree.css_first('link[rel="canonical"]')
    og = {}
    for node in tree.css('meta[property^="og:"]'):
        value = _collapse(node.attributes.get("content") or "")
        if value:
            og[node.attributes["property"]] = value
    found = {
        "description": meta('meta[name="description"]'),
        "language": (tree.root.attributes.get("lang") or "").strip() if tree.root else "",
        "canonical_url": (canonical.attributes.get("href") or "").strip() if canonical else "",
        "og": og,
    }
    return {key: value for key, value in found.items() if value}


def extract(page: FetchedPage) -> ExtractedDocument:
    """Sync and pure: decode, strip noise, walk blocks, build the hash."""
    tree = LexborHTMLParser(_decode(page))
    metadata = _metadata(tree)

    blocks: list[Block] = []
    if tree.body is not None:
        _walk_blocks(tree.body, blocks)
    if not blocks:
        raise ExtractionError(ExtractionErrorReason.EMPTY_CONTENT, f"no content: {page.final_url}")

    title_node = tree.css_first("title")
    first_h1 = next((b.text for b in blocks if b.type == "heading" and b.level == 1), "")
    title = (
        (_collapse(title_node.text()) if title_node else "")
        or metadata.get("og", {}).get("og:title", "")
        or first_h1
        or page.final_url
    )

    document = ExtractedDocument(
        source_uri=page.final_url,
        title=title,
        mime_type=page.mime_type,
        content_hash="",
        requested_url=page.requested_url,
        status_code=page.status_code,
        fetched_at=page.fetched_at,
        metadata=metadata,
        blocks=blocks,
        sections=_build_sections(blocks),
        links=_extract_links(tree, page.final_url),
    )
    normalised = unicodedata.normalize("NFC", document.text())
    document.content_hash = hashlib.sha256(normalised.encode("utf-8")).hexdigest()
    return document


async def extract_url(client: httpx.AsyncClient, url: str) -> ExtractedDocument:
    page = await fetch_page(client, url)
    # SYNC-EXCEPTION: selectolax has no async API; parsing runs via asyncio.to_thread in the worker
    return await asyncio.to_thread(extract, page)
