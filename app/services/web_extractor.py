import asyncio
import codecs
import hashlib
import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from urllib.parse import urlsplit

import httpx
from selectolax.lexbor import LexborHTMLParser, LexborNode

from app.core.config import settings
from app.schemas.extracted_document import Block, ExtractedDocument

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
# emitted once, whole, and not recursed into (slice 4 gives them their own types)
BLOCK_TAGS = frozenset("h1 h2 h3 h4 h5 h6 p figcaption ul ol table pre blockquote".split())
INLINE_TAGS = frozenset(
    "a abbr b bdi bdo cite code data dfn em i kbd mark q s samp small span strong sub sup time "
    "u var wbr".split()
)


class ExtractionErrorReason(StrEnum):
    INVALID_URL = "invalid_url"
    HTTP_STATUS = "http_status"
    TOO_LARGE = "too_large"
    NOT_HTML = "not_html"
    EMPTY_CONTENT = "empty_content"


class ExtractionError(Exception):
    def __init__(
        self, reason: ExtractionErrorReason, message: str, *, status_code: int | None = None
    ):
        super().__init__(message)
        self.reason = reason
        self.status_code = status_code


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


def _is_skipped(node: LexborNode) -> bool:
    if node.tag in NOISE_TAGS:
        return True
    attrs = node.attributes
    return "hidden" in attrs or attrs.get("aria-hidden") == "true"


def _text_of(node: LexborNode) -> str:
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
            elif not _is_skipped(child):
                spaced = tag == "br" or tag not in INLINE_TAGS
                if spaced:
                    parts.append(" ")
                collect(child)
                if spaced:
                    parts.append(" ")
            child = child.next

    collect(node)
    return _collapse("".join(parts))


def _walk_blocks(parent: LexborNode, blocks: list[Block]) -> None:
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
        elif tag.startswith("-") or _is_skipped(child):
            pass
        elif tag in BLOCK_TAGS:
            flush()
            if text := _text_of(child):
                blocks.append(Block(type="paragraph", text=text))
        elif tag in INLINE_TAGS or tag == "br":
            loose.append(" " if tag == "br" else _text_of(child))
        else:
            flush()
            _walk_blocks(child, blocks)
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
    title = (
        (_collapse(title_node.text()) if title_node else "")
        or metadata.get("og", {}).get("og:title", "")
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
    )
    normalised = unicodedata.normalize("NFC", document.text())
    document.content_hash = hashlib.sha256(normalised.encode("utf-8")).hexdigest()
    return document


async def extract_url(client: httpx.AsyncClient, url: str) -> ExtractedDocument:
    page = await fetch_page(client, url)
    return await asyncio.to_thread(extract, page)
