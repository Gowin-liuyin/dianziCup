"""Bounded arXiv Atom metadata parsing; raw XML remains the caller's evidence."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlsplit, urlunsplit
from xml.etree import ElementTree

from ai_intel.ingestion.sources.academic import (
    AcademicContractError,
    AcademicRecord,
    normalize_academic_record,
)

ATOM = "{http://www.w3.org/2005/Atom}"
ARXIV = "{http://arxiv.org/schemas/atom}"
OPENSEARCH = "{http://a9.com/-/spec/opensearch/1.1/}"
MAX_PAYLOAD_BYTES = 2 * 1024 * 1024
MAX_ENTRIES = 1000
MAX_XML_NODES = 10000
MAX_XML_DEPTH = 32
ARXIV_VERSION_ID = re.compile(
    r"(?P<paper>\d{4}\.\d{4,5}|[a-zA-Z][a-zA-Z.-]*/\d{7})(?P<version>v[1-9]\d*)"
)


@dataclass(frozen=True)
class ArxivDiscoveryPage:
    """Upstream page counts are retained, never inferred from an empty record list."""

    records: tuple[AcademicRecord, ...]
    total_results: int
    start_index: int
    items_per_page: int


class _BoundedAtomTreeBuilder(ElementTree.TreeBuilder):
    def __init__(self) -> None:
        super().__init__()
        self.node_count = 0
        self.depth = 0

    def start(self, tag: str, attrs: dict[str, str]) -> ElementTree.Element:
        self.node_count += 1
        self.depth += 1
        if self.node_count > MAX_XML_NODES or self.depth > MAX_XML_DEPTH:
            raise AcademicContractError("arXiv XML structural limit exceeded")
        if "{http://www.w3.org/XML/1998/namespace}base" in attrs:
            raise AcademicContractError("arXiv XML base overrides are unsupported")
        return super().start(tag, attrs)

    def end(self, tag: str) -> ElementTree.Element:
        self.depth -= 1
        return super().end(tag)

    def doctype(self, name: str, pubid: str | None, system: str | None) -> None:
        raise AcademicContractError("arXiv DTD and entity declarations are forbidden")


def _parse_xml(payload: bytes) -> ElementTree.Element:
    if not payload or len(payload) > MAX_PAYLOAD_BYTES:
        raise AcademicContractError("arXiv payload must contain 1..2097152 bytes")
    try:
        decoded = payload.decode("utf-8-sig")
        declaration = re.match(r"\s*<\?xml\b[^?]*\?>", decoded)
        if declaration:
            encoding = re.search(r'encoding\s*=\s*[\'"]([^\'"]+)[\'"]', declaration[0])
            if encoding and encoding[1].casefold() != "utf-8":
                raise AcademicContractError("arXiv XML encoding must be UTF-8")
        parser = ElementTree.XMLParser(target=_BoundedAtomTreeBuilder())
        parser.feed(decoded)
        return parser.close()
    except (UnicodeError, ElementTree.ParseError, ValueError):
        raise AcademicContractError("arXiv malformed XML or unsupported encoding") from None


def _text(parent: ElementTree.Element, tag: str, required: bool = False) -> str | None:
    children = parent.findall(tag)
    if len(children) > 1 or (required and not children):
        raise AcademicContractError("arXiv missing or duplicate metadata field")
    if not children:
        return None
    child = children[0]
    if len(child):
        raise AcademicContractError("arXiv metadata field must contain plain text")
    value = (child.text or "").strip()
    if not value:
        raise AcademicContractError("arXiv empty metadata field")
    return value


def _official_uri(raw_uri: str) -> str:
    """Only historical arxiv.org HTTP identifiers map to the same HTTPS authority."""
    if (
        any(
            character.isspace() or ord(character) < 32 or ord(character) == 127
            for character in raw_uri
        )
        or "\\" in raw_uri
    ):
        raise AcademicContractError("arXiv URI contains invalid characters")
    try:
        parts = urlsplit(raw_uri)
        if parts.scheme not in {"https", "http"} or parts.netloc != "arxiv.org" or parts.fragment:
            raise AcademicContractError("arXiv URI must use the fixed official origin")
        return urlunsplit(("https", parts.netloc, parts.path, parts.query, ""))
    except ValueError:
        raise AcademicContractError("arXiv invalid URI") from None


def _utc_time(value: str | None) -> str | None:
    if value is None:
        return None
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value):
        raise AcademicContractError("arXiv timestamp must explicitly use UTC Z")
    try:
        datetime.fromisoformat(value)
    except ValueError:
        raise AcademicContractError("arXiv invalid timestamp") from None
    return value


def _license_identifier(value: str | None) -> str | None:
    """Licence identifiers remain unverified source text, never fetch or redistribution grants."""
    if value is None:
        return None
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise AcademicContractError("arXiv licence identifier contains control characters")
    if not re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", value):
        return value
    try:
        parts = urlsplit(value)
        if (
            parts.scheme not in {"https", "http"}
            or parts.hostname is None
            or parts.username is not None
            or parts.password is not None
            or parts.port is not None
            or any(character.isspace() for character in value)
            or "\\" in value
        ):
            raise AcademicContractError("arXiv licence identifier contains an unsafe URI")
    except ValueError:
        raise AcademicContractError("arXiv licence identifier contains an invalid URI") from None
    return value


def _parse_record(entry: ElementTree.Element) -> AcademicRecord:
    entry_uri = _text(entry, ATOM + "id", required=True)
    assert entry_uri is not None
    parts = urlsplit(_official_uri(entry_uri))
    identifier = parts.path.removeprefix("/abs/")
    match = ARXIV_VERSION_ID.fullmatch(identifier)
    if not parts.path.startswith("/abs/") or parts.query or match is None:
        raise AcademicContractError("arXiv entry must identify an explicit paper version")
    title = _text(entry, ATOM + "title", required=True)
    assert title is not None
    authors: list[str] = []
    for author in entry.findall(ATOM + "author"):
        name = _text(author, ATOM + "name", required=True)
        assert name is not None
        authors.append(name)
        author_uri = _text(author, ATOM + "uri")
        if author_uri is not None:
            _official_uri(author_uri)
    if not authors:
        raise AcademicContractError("arXiv entry is missing authors")
    published = _utc_time(_text(entry, ATOM + "published"))
    modified = _utc_time(_text(entry, ATOM + "updated"))
    if published is not None and modified is not None and modified < published:
        raise AcademicContractError("arXiv update precedes original publication")
    pdf_uri: str | None = None
    for link in entry.findall(ATOM + "link"):
        href = link.get("href")
        if href is None:
            raise AcademicContractError("arXiv link is missing href")
        uri = _official_uri(href)
        link_parts = urlsplit(uri)
        if link_parts.query or link_parts.path not in {f"/abs/{identifier}", f"/pdf/{identifier}"}:
            raise AcademicContractError("arXiv link refers to a different paper version")
        if link.get("title") == "pdf" or link.get("type") == "application/pdf":
            if link_parts.path != f"/pdf/{identifier}" or pdf_uri is not None:
                raise AcademicContractError("arXiv conflicting PDF links")
            pdf_uri = uri
    license_identifier = _license_identifier(_text(entry, ARXIV + "license"))
    comment = _text(entry, ARXIV + "comment")
    withdrawn = (
        comment is not None
        and re.match(
            r"^This (?:paper|article) has been withdrawn(?:\.|\s+(?:by|due to|because)\b)",
            comment,
            re.IGNORECASE,
        )
        is not None
    )
    return normalize_academic_record(
        {
            "paper_id": "arxiv:" + match["paper"],
            "version": match["version"],
            "title": " ".join(title.split()),
            "authors": authors,
            "abstract": _text(entry, ATOM + "summary"),
            "published_at": published,
            "modified_at": modified,
            "full_text_link": pdf_uri,
            "license": license_identifier,
            "withdrawn": withdrawn,
        }
    )


def parse_arxiv_atom(payload: bytes) -> ArxivDiscoveryPage:
    """Parse one fixed-origin metadata page, refusing malformed or truncated page semantics."""
    root = _parse_xml(payload)
    if root.tag != ATOM + "feed":
        raise AcademicContractError("arXiv response is not an Atom feed")
    uri = _text(root, ATOM + "id")
    if uri is not None:
        _official_uri(uri)
    for link in root.findall(ATOM + "link"):
        href = link.get("href")
        if href is None:
            raise AcademicContractError("arXiv feed link is missing href")
        _official_uri(href)
    counts: list[int] = []
    for field in ("totalResults", "startIndex", "itemsPerPage"):
        value = _text(root, OPENSEARCH + field, required=True)
        if value is None or not re.fullmatch(r"\d{1,12}", value):
            raise AcademicContractError("arXiv page count must be a nonnegative bounded integer")
        counts.append(int(value))
    total, start, size = counts
    entries = root.findall(ATOM + "entry")
    entry_elements = set(entries)
    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1] == "entry" and element not in entry_elements:
            raise AcademicContractError("arXiv entry has an unexpected namespace or nesting")
    if size > MAX_ENTRIES or len(entries) > MAX_ENTRIES or len(entries) > size:
        raise AcademicContractError("arXiv entry count exceeds the reported page or local limit")
    if start > total or start + len(entries) > total or (not entries and start < total):
        raise AcademicContractError("arXiv page counts conflict with entries")
    if len(entries) < min(size, total - start):
        raise AcademicContractError("arXiv discovery page is incomplete")
    records = tuple(_parse_record(entry) for entry in entries)
    identities = {(record.paper_id, record.version_label) for record in records}
    if len(identities) != len(records):
        raise AcademicContractError("arXiv page contains duplicate paper versions")
    return ArxivDiscoveryPage(records, total, start, size)
