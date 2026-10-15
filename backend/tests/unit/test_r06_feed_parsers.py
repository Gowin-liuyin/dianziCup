"""Explicit synthetic XML fixtures exercise source boundaries without network IO."""

from __future__ import annotations

import socket
from collections.abc import Callable
from dataclasses import FrozenInstanceError

import pytest

from ai_intel.ingestion.sources.academic import AcademicContractError
from ai_intel.ingestion.sources.arxiv_atom import parse_arxiv_atom
from ai_intel.ingestion.sources.feed import FeedParseError
from ai_intel.ingestion.sources.trailofbits_rss import parse_trailofbits_rss


def atom_entry(identifier: str = "2609.05903v2", extra: str = "") -> str:
    return f"""<entry><id>http://arxiv.org/abs/{identifier}</id>
    <title>提示注入研究</title><published>2026-09-05T05:56:41Z</published>
    <updated>2026-10-14T08:52:25Z</updated><author><name>Researcher</name></author>
    <summary>Paper claims, not confirmed asset impact.</summary>
    <link href="https://arxiv.org/abs/{identifier}" rel="alternate"/>
    <link href="https://arxiv.org/pdf/{identifier}" title="pdf"/>{extra}</entry>"""


def atom_page(entries: str | None = None, total: int = 1, start: int = 0, size: int = 1) -> bytes:
    content = atom_entry() if entries is None else entries
    return f"""<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom"
    xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/"
    xmlns:arxiv="http://arxiv.org/schemas/atom">
    <id>https://arxiv.org/api/test</id>
    <opensearch:totalResults>{total}</opensearch:totalResults>
    <opensearch:startIndex>{start}</opensearch:startIndex>
    <opensearch:itemsPerPage>{size}</opensearch:itemsPerPage>{content}</feed>""".encode()


def rss_item(
    link: str = "https://blog.trailofbits.com/2026/10/14/article/", extra: str = ""
) -> str:
    return f"""<item><title>Security research</title><link>{link}</link>
    <pubDate>Wed, 14 Oct 2026 07:00:00 -0400</pubDate>
    <guid>opaque-guid</guid><description>&lt;p&gt;Feed excerpt&lt;/p&gt;</description>
    {extra}</item>"""


def rss_page(items: str | None = None) -> bytes:
    content = rss_item() if items is None else items
    return f"""<rss version="2.0"><channel><title>The Trail of Bits Blog</title>
    <link>https://blog.trailofbits.com/</link>
    <lastBuildDate>Thu, 15 Oct 2026 12:00:00 +0000</lastBuildDate>
    {content}</channel></rss>""".encode()


def test_arxiv_version_time_and_metadata_are_distinct() -> None:
    page = parse_arxiv_atom(atom_page())
    record = page.records[0]
    assert record.paper_id == "arxiv:2609.05903"
    assert record.version_label == "v2"
    assert record.published_at == "2026-09-05T05:56:41Z"
    assert record.modified_at == "2026-10-14T08:52:25Z"
    assert record.title == "提示注入研究"
    assert record.full_text_link == "https://arxiv.org/pdf/2609.05903v2"
    assert record.full_text_fetched is False and record.extraction_status == "metadata_only"
    assert page.total_results == 1 and page.start_index == 0 and page.items_per_page == 1


@pytest.mark.parametrize(
    "field_name", ["total_results", "records", "start_index", "items_per_page"]
)
def test_arxiv_discovery_page_is_immutable(field_name: str) -> None:
    page = parse_arxiv_atom(atom_page())
    with pytest.raises(FrozenInstanceError):
        setattr(page, field_name, 2)


def test_arxiv_versions_share_identity_but_keep_revision() -> None:
    entries = atom_entry("2609.05903v1") + atom_entry("2609.05903v2")
    records = parse_arxiv_atom(atom_page(entries, total=2, size=2)).records
    assert records[0].paper_id == records[1].paper_id
    assert tuple(record.version_label for record in records) == ("v1", "v2")
    legacy = parse_arxiv_atom(atom_page(atom_entry("math.GT/0309136v1"))).records[0]
    assert legacy.paper_id == "arxiv:math.GT/0309136" and legacy.version_label == "v1"


def test_arxiv_explicit_withdrawal_only() -> None:
    explicit = atom_entry(
        extra="<arxiv:comment>This paper has been withdrawn by the author.</arxiv:comment>"
    )
    assert parse_arxiv_atom(atom_page(explicit)).records[0].withdrawn is True
    discussion = atom_entry(extra="<arxiv:comment>We study withdrawn papers.</arxiv:comment>")
    assert parse_arxiv_atom(atom_page(discussion)).records[0].withdrawn is False
    titled = atom_page().replace("提示注入研究".encode(), b"WITHDRAWN research")
    assert parse_arxiv_atom(titled).records[0].withdrawn is False
    question = atom_entry(
        extra="<arxiv:comment>This paper has been withdrawn? Quoted question.</arxiv:comment>"
    )
    assert parse_arxiv_atom(atom_page(question)).records[0].withdrawn is False


@pytest.mark.parametrize(
    "identifier",
    [
        "https://creativecommons.org/licenses/by/4.0/",
        "https://creativecommons.org/publicdomain/zero/1.0/",
        "https://arxiv.org/licenses/nonexclusive-distrib/1.0/",
        "Unverified publisher licence",
        "https://publisher.invalid/unverified-licence",
    ],
)
def test_arxiv_licence_identifiers_are_preserved_without_dereferencing(
    identifier: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbid_network(*args: object, **kwargs: object) -> None:
        raise AssertionError("metadata parsing must not open a network connection")

    monkeypatch.setattr(socket, "socket", forbid_network)
    entry = atom_entry(extra=f"<arxiv:license>{identifier}</arxiv:license>")
    record = parse_arxiv_atom(atom_page(entry)).records[0]
    assert record.license_identifier == identifier
    assert record.full_text_fetched is False


@pytest.mark.parametrize(
    "identifier",
    [
        "javascript:alert(1)",
        "data:text/plain,grant",
        "file:///private",
        "https://user@creativecommons.org/licenses/by/4.0/",
        "https://creativecommons.org/licenses/by/4.0/&#10;bad",
    ],
)
def test_arxiv_unsafe_licence_uri_is_rejected(identifier: str) -> None:
    with pytest.raises(AcademicContractError):
        parse_arxiv_atom(
            atom_page(atom_entry(extra=f"<arxiv:license>{identifier}</arxiv:license>"))
        )


@pytest.mark.parametrize(
    "identifier", ["2609.05903", "2609.05903v0", "not-a-paper", "2609.05903v01"]
)
def test_arxiv_requires_explicit_valid_version(identifier: str) -> None:
    with pytest.raises(AcademicContractError):
        parse_arxiv_atom(atom_page(atom_entry(identifier)))


@pytest.mark.parametrize(
    "total,start,size", [(-1, 0, 1), (1, -1, 1), (1, 2, 1), (1, 0, 0), (1, 0, 1001)]
)
def test_arxiv_rejects_conflicting_page_bounds(total: int, start: int, size: int) -> None:
    with pytest.raises(AcademicContractError):
        parse_arxiv_atom(atom_page(total=total, start=start, size=size))


def test_arxiv_empty_and_last_page_keep_original_pagination() -> None:
    empty = parse_arxiv_atom(atom_page("", total=0, size=2))
    assert empty.records == () and empty.items_per_page == 2
    last = parse_arxiv_atom(atom_page(total=11, start=10, size=2))
    assert last.total_results == 11 and len(last.records) == 1 and last.items_per_page == 2


@pytest.mark.parametrize(
    "change",
    [
        ("2026-10-14T08:52:25Z", "2026-10-14T08:52:25"),
        ("2026-10-14T08:52:25Z", "2026-02-30T08:52:25Z"),
        ("2026-10-14T08:52:25Z", "2025-10-14T08:52:25Z"),
        ("<title>提示注入研究</title>", "<title>A</title><title>B</title>"),
        ("<author><name>Researcher</name></author>", "<author/>"),
        ("<opensearch:totalResults>1</opensearch:totalResults>", ""),
    ],
)
def test_arxiv_missing_conflicting_or_malformed_fields(change: tuple[str, str]) -> None:
    payload = atom_page().decode().replace(*change).encode()
    with pytest.raises(AcademicContractError):
        parse_arxiv_atom(payload)


def test_arxiv_missing_optional_fields_remain_unknown() -> None:
    payload = atom_page().replace(b"<published>2026-09-05T05:56:41Z</published>", b"")
    payload = payload.replace(b"<summary>Paper claims, not confirmed asset impact.</summary>", b"")
    record = parse_arxiv_atom(payload).records[0]
    assert record.published_at is None and record.abstract is None
    future = parse_arxiv_atom(atom_page().replace(b"2026-10-14T08:52:25Z", b"2099-10-14T08:52:25Z"))
    assert future.records[0].modified_at == "2099-10-14T08:52:25Z"


@pytest.mark.parametrize(
    "uri",
    [
        "https://evil.invalid/abs/2609.05903v2",
        "https://arxiv.org.evil.invalid/abs/2609.05903v2",
        "https://user@arxiv.org/abs/2609.05903v2",
        "https://arxiv.org:444/abs/2609.05903v2",
        "https://arxiv.org/abs/2609.05903v3",
        "https://arxiv.org\\evil.invalid/abs/2609.05903v2",
    ],
)
def test_arxiv_link_identity_and_origin_are_validated(uri: str) -> None:
    payload = atom_page().replace(b"https://arxiv.org/abs/2609.05903v2", uri.encode())
    with pytest.raises(AcademicContractError):
        parse_arxiv_atom(payload)


def test_arxiv_duplicate_version_is_not_silently_dropped() -> None:
    with pytest.raises(AcademicContractError):
        parse_arxiv_atom(atom_page(atom_entry() * 2, total=2, size=2))


def test_rss_description_identity_and_original_time_scope() -> None:
    entry = parse_trailofbits_rss(rss_page())[0]
    assert entry.published_at == "2026-10-14T11:00:00Z"
    assert entry.modified_at is None
    assert entry.body_text == "<p>Feed excerpt</p>"
    assert entry.missing_fields == ("modified", "article_body")
    changed = rss_page().replace(b"opaque-guid", b"other-guid")
    assert parse_trailofbits_rss(changed)[0].source_record_id == entry.source_record_id


def test_rss_tracking_queries_and_revisions_preserve_identity() -> None:
    first = parse_trailofbits_rss(
        rss_page(rss_item("https://blog.trailofbits.com/a?id=1&amp;utm_source=rss"))
    )[0]
    second = parse_trailofbits_rss(
        rss_page(rss_item("https://blog.trailofbits.com/a?id=1&amp;fbclid=other"))
    )[0]
    third = parse_trailofbits_rss(rss_page(rss_item("https://blog.trailofbits.com/a?id=2")))[0]
    assert first.source_record_id == second.source_record_id
    assert first.canonical_uri == "https://blog.trailofbits.com/a?id=1"
    assert third.source_record_id != first.source_record_id
    revised = parse_trailofbits_rss(rss_page().replace(b"Feed excerpt", b"Revised excerpt"))[0]
    original = parse_trailofbits_rss(rss_page())[0]
    assert revised.source_record_id == original.source_record_id
    assert revised.content_hash_sha256 != original.content_hash_sha256


def test_rss_missing_time_and_description_do_not_become_successful_full_text() -> None:
    payload = rss_page().replace(b"<pubDate>Wed, 14 Oct 2026 07:00:00 -0400</pubDate>", b"")
    payload = payload.replace(b"<description>&lt;p&gt;Feed excerpt&lt;/p&gt;</description>", b"")
    entry = parse_trailofbits_rss(payload)[0]
    assert entry.published_at is None and entry.body_text is None
    assert set(entry.missing_fields) == {"published", "modified", "body", "article_body"}
    assert parse_trailofbits_rss(rss_page("")) == ()


@pytest.mark.parametrize(
    "date", ["Wed, 14 Oct 2026 07:00:00", "not-a-date", "Wed, 32 Oct 2026 07:00:00 +0000"]
)
def test_rss_time_without_valid_explicit_zone_is_rejected(date: str) -> None:
    payload = rss_page().replace(b"Wed, 14 Oct 2026 07:00:00 -0400", date.encode())
    with pytest.raises(FeedParseError):
        parse_trailofbits_rss(payload)


@pytest.mark.parametrize(
    "uri",
    [
        "http://blog.trailofbits.com/a",
        "https://evil.invalid/a",
        "https://blog.trailofbits.com.evil.invalid/a",
        "https://user@blog.trailofbits.com/a",
        "https://blog.trailofbits.com:444/a",
        "//blog.trailofbits.com/a",
        "https://blog.trailofbits.com/\x01a",
    ],
)
def test_rss_official_https_origin_required(uri: str) -> None:
    with pytest.raises(FeedParseError):
        parse_trailofbits_rss(rss_page(rss_item(uri)))


def test_rss_structural_change_and_duplicates_fail_whole_page() -> None:
    for payload in [
        b'<rss version="2.0"/>',
        rss_page().replace(b"<title>Security research</title>", b""),
        rss_page(rss_item() * 2),
    ]:
        with pytest.raises(FeedParseError):
            parse_trailofbits_rss(payload)


@pytest.mark.parametrize(
    "parser,error",
    [(parse_arxiv_atom, AcademicContractError), (parse_trailofbits_rss, FeedParseError)],
)
@pytest.mark.parametrize(
    "payload",
    [
        b'<!DOCTYPE feed [<!ENTITY x "injected">]><feed>&x;</feed>',
        b'<!DOCTYPE feed SYSTEM "file:///private"><feed/>',
        b"<feed>&unknown;</feed>",
        b"<feed>",
        b'<?xml version="1.0" encoding="ISO-8859-1"?><feed/>',
        b"\xff<feed/>",
        b"<feed>" + b"<child>" * 33 + b"</child>" * 33 + b"</feed>",
        b"<feed>" + b"<child/>" * 10001 + b"</feed>",
        b" " * (2 * 1024 * 1024 + 1),
    ],
    ids=[
        "internal-entity",
        "external-dtd",
        "unknown-entity",
        "malformed",
        "encoding",
        "invalid-utf8",
        "depth-limit",
        "node-limit",
        "byte-limit",
    ],
)
def test_xml_security_and_resource_limits(
    parser: Callable[[bytes], object], error: type[Exception], payload: bytes
) -> None:
    with pytest.raises(error):
        parser(payload)


def test_entry_count_limit_does_not_truncate() -> None:
    with pytest.raises(FeedParseError):
        parse_trailofbits_rss(rss_page(rss_item() * 1001))


@pytest.mark.parametrize("attribute", ['xml:base="https://evil.invalid/"'])
def test_xml_base_cannot_redirect_source_link_resolution(attribute: str) -> None:
    with pytest.raises(AcademicContractError):
        parse_arxiv_atom(atom_page().replace(b"<entry>", f"<entry {attribute}>".encode()))
    with pytest.raises(FeedParseError):
        parse_trailofbits_rss(rss_page().replace(b"<item>", f"<item {attribute}>".encode()))


def test_nested_and_wrong_namespace_records_cannot_disappear() -> None:
    atom_payload = atom_page().replace(b"<entry>", b'<entry xmlns="https://evil.invalid">')
    with pytest.raises(AcademicContractError):
        parse_arxiv_atom(atom_payload)
    with pytest.raises(AcademicContractError):
        parse_arxiv_atom(atom_page("<container>" + atom_entry() + "</container>"))
    with pytest.raises(FeedParseError):
        parse_trailofbits_rss(rss_page("<container>" + rss_item() + "</container>"))
    with pytest.raises(FeedParseError):
        parse_trailofbits_rss(rss_page().replace(b"<item>", b'<item xmlns="https://evil.invalid">'))


def test_discovery_page_exact_byte_budget_is_accepted() -> None:
    atom = atom_page()
    assert len(parse_arxiv_atom(atom + b" " * (2 * 1024 * 1024 - len(atom))).records) == 1
    rss = rss_page()
    assert len(parse_trailofbits_rss(rss + b" " * (2 * 1024 * 1024 - len(rss)))) == 1


def test_secondary_xml_links_must_match_official_origin() -> None:
    atom = atom_page().replace(b"https://arxiv.org/api/test", b"https://evil.invalid/api/test")
    with pytest.raises(AcademicContractError):
        parse_arxiv_atom(atom)
    with pytest.raises(AcademicContractError):
        parse_arxiv_atom(
            atom_page().replace(b"https://arxiv.org/pdf/", b"https://evil.invalid/pdf/")
        )
    with pytest.raises(FeedParseError):
        parse_trailofbits_rss(rss_page().replace(b"opaque-guid", b"https://evil.invalid/article"))


def test_entity_like_literals_in_text_are_not_expanded() -> None:
    payload = atom_page().replace(
        b"Paper claims, not confirmed asset impact.",
        b"&lt;!DOCTYPE harmless&gt; &amp; named entity text",
    )
    assert parse_arxiv_atom(payload).records[0].abstract == (
        "<!DOCTYPE harmless> & named entity text"
    )
