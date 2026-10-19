"""Fixed-origin Trail of Bits discovery; feed description never proves article fetch."""

from __future__ import annotations

import re
from dataclasses import replace
from datetime import UTC
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit
from xml.etree import ElementTree

from ai_intel.ingestion.sources.feed import FeedEntry, FeedParseError, normalize_feed_entry

ATOM = "{http://www.w3.org/2005/Atom}"
MAX_PAYLOAD_BYTES = 2 * 1024 * 1024
MAX_ENTRIES = 1000
MAX_XML_NODES = 10000
MAX_XML_DEPTH = 32


class _BoundedRssTreeBuilder(ElementTree.TreeBuilder):
    def __init__(self) -> None:
        super().__init__()
        self.node_count = 0
        self.depth = 0

    def start(self, tag: str, attrs: dict[str, str]) -> ElementTree.Element:
        self.node_count += 1
        self.depth += 1
        if self.node_count > MAX_XML_NODES or self.depth > MAX_XML_DEPTH:
            raise FeedParseError("Trail of Bits XML structural limit exceeded")
        if "{http://www.w3.org/XML/1998/namespace}base" in attrs:
            raise FeedParseError("Trail of Bits XML base overrides are unsupported")
        return super().start(tag, attrs)

    def end(self, tag: str) -> ElementTree.Element:
        self.depth -= 1
        return super().end(tag)

    def doctype(self, name: str, pubid: str | None, system: str | None) -> None:
        raise FeedParseError("Trail of Bits DTD and entity declarations are forbidden")


def _parse_xml(payload: bytes) -> ElementTree.Element:
    if not payload or len(payload) > MAX_PAYLOAD_BYTES:
        raise FeedParseError("Trail of Bits payload must contain 1..2097152 bytes")
    try:
        decoded = payload.decode("utf-8-sig")
        declaration = re.match(r"\s*<\?xml\b[^?]*\?>", decoded)
        if declaration:
            encoding = re.search(r'encoding\s*=\s*[\'"]([^\'"]+)[\'"]', declaration[0])
            if encoding and encoding[1].casefold() != "utf-8":
                raise FeedParseError("Trail of Bits XML encoding must be UTF-8")
        parser = ElementTree.XMLParser(target=_BoundedRssTreeBuilder())
        parser.feed(decoded)
        return parser.close()
    except (UnicodeError, ElementTree.ParseError, ValueError):
        raise FeedParseError("Trail of Bits malformed XML or unsupported encoding") from None


def _text(parent: ElementTree.Element, tag: str, required: bool = False) -> str | None:
    children = parent.findall(tag)
    if len(children) > 1 or (required and not children):
        raise FeedParseError("Trail of Bits missing or duplicate RSS field")
    if not children:
        return None
    child = children[0]
    if len(child):
        raise FeedParseError("Trail of Bits RSS field must contain text")
    value = (child.text or "").strip()
    if not value:
        raise FeedParseError("Trail of Bits empty RSS field")
    return value


def _official_uri(raw_uri: str) -> str:
    if (
        any(
            character.isspace() or ord(character) < 32 or ord(character) == 127
            for character in raw_uri
        )
        or "\\" in raw_uri
    ):
        raise FeedParseError("Trail of Bits URI contains invalid characters")
    try:
        parts = urlsplit(raw_uri)
        if parts.scheme != "https" or parts.netloc != "blog.trailofbits.com":
            raise FeedParseError("Trail of Bits URI must use the fixed official HTTPS origin")
    except ValueError:
        raise FeedParseError("Trail of Bits invalid URI") from None
    return raw_uri


def _timezone_token(raw_value: str) -> str | None:
    """Select the zone using Python 3.12's field layout, leaving date interpretation to stdlib."""
    fields = raw_value.split()
    if not fields:
        return None
    if fields[0].endswith(",") or fields[0].lower() in (
        "mon",
        "tue",
        "wed",
        "thu",
        "fri",
        "sat",
        "sun",
    ):
        fields = fields[1:]
    else:
        comma = fields[0].rfind(",")
        if comma >= 0:
            fields[0] = fields[0][comma + 1 :]
    if len(fields) == 3:
        date_fields = fields[0].split("-")
        if len(date_fields) == 3:
            fields = date_fields + fields[1:]
    if len(fields) == 4:
        zone_start = fields[3].find("+")
        if zone_start < 0:
            zone_start = fields[3].find("-")
        if zone_start > 0:
            fields[3:] = [fields[3][:zone_start], fields[3][zone_start:]]
        else:
            fields.append("")
    if len(fields) < 5:
        return None
    year = fields[2]
    if year.find(":") > 0:
        year = fields[3]
    year = year.removesuffix(",")
    if not year:
        return None
    return fields[4] if year[0].isdigit() else year


def _published_at(raw_value: str | None) -> str | None:
    if raw_value is None:
        return None
    zone = _timezone_token(raw_value)
    if zone is not None:
        try:
            numeric_zone = abs(int(zone))
        except ValueError:
            pass
        else:
            if numeric_zone // 100 > 23 or numeric_zone % 100 > 59:
                raise FeedParseError("Trail of Bits numeric timezone fields are out of range")
    try:
        value = parsedate_to_datetime(raw_value)
        if value.tzinfo is None or value.utcoffset() is None:
            raise FeedParseError("Trail of Bits publication time lacks an explicit timezone")
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
    except (ValueError, OverflowError, TypeError):
        raise FeedParseError("Trail of Bits invalid publication time") from None


def parse_trailofbits_rss(payload: bytes) -> tuple[FeedEntry, ...]:
    """Retain every valid item or fail the page; never promote feed content to article evidence."""
    root = _parse_xml(payload)
    channels = root.findall("channel")
    if root.tag != "rss" or root.get("version") != "2.0" or len(channels) != 1:
        raise FeedParseError("Trail of Bits response is not the expected RSS 2.0 channel")
    channel = channels[0]
    channel_uri = _text(channel, "link", required=True)
    assert channel_uri is not None
    _official_uri(channel_uri)
    for parent in (channel, *channel.findall("item")):
        for atom_link in parent.findall(ATOM + "link"):
            href = atom_link.get("href")
            if href is None:
                raise FeedParseError("Trail of Bits Atom link is missing href")
            _official_uri(href)
    items = channel.findall("item")
    item_elements = set(items)
    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1] == "item" and element not in item_elements:
            raise FeedParseError("Trail of Bits item has an unexpected namespace or nesting")
    if len(items) > MAX_ENTRIES:
        raise FeedParseError("Trail of Bits RSS exceeds the item limit")
    records: list[FeedEntry] = []
    for item in items:
        link = _text(item, "link", required=True)
        title = _text(item, "title", required=True)
        assert link is not None and title is not None
        guid = _text(item, "guid")
        if guid is not None and ("://" in guid or guid.startswith("//")):
            _official_uri(guid)
        entry = normalize_feed_entry(
            {
                "link": _official_uri(link),
                "title": title,
                "published": _published_at(_text(item, "pubDate")),
                "modified": None,
                "body": _text(item, "description"),
            },
            "trailofbits",
        )
        records.append(replace(entry, missing_fields=(*entry.missing_fields, "article_body")))
    if len({entry.source_record_id for entry in records}) != len(records):
        raise FeedParseError("Trail of Bits RSS contains duplicate canonical article identities")
    return tuple(records)
