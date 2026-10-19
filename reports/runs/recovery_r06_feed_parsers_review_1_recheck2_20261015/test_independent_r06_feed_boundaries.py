"""Independent synthetic parser cases; no network, model judging or holdout inputs."""

from __future__ import annotations

import socket
from collections.abc import Callable
from dataclasses import FrozenInstanceError

import pytest

from ai_intel.ingestion.sources.academic import AcademicContractError
from ai_intel.ingestion.sources.arxiv_atom import parse_arxiv_atom
from ai_intel.ingestion.sources.feed import FeedParseError
from ai_intel.ingestion.sources.trailofbits_rss import parse_trailofbits_rss


def entry(identifier: str = "2610.00001v1", extra: str = "") -> str:
    return (
        f"<entry><id>https://arxiv.org/abs/{identifier}</id><title>Boundary paper</title>"
        f"<author><name>Independent author</name></author>{extra}</entry>"
    )


def atom(records: str = "", total: int = 0, start: int = 0, size: int = 0) -> bytes:
    return (
        '<feed xmlns="http://www.w3.org/2005/Atom" '
        'xmlns:o="http://a9.com/-/spec/opensearch/1.1/" '
        'xmlns:arxiv="http://arxiv.org/schemas/atom">'
        f"<o:totalResults>{total}</o:totalResults><o:startIndex>{start}</o:startIndex>"
        f"<o:itemsPerPage>{size}</o:itemsPerPage>{records}</feed>"
    ).encode()


def item(uri: str = "https://blog.trailofbits.com/review/", extra: str = "") -> str:
    return f"<item><title>Boundary article</title><link>{uri}</link>{extra}</item>"


def rss(records: str = "") -> bytes:
    return (
        '<rss version="2.0"><channel><link>https://blog.trailofbits.com/</link>'
        f"{records}</channel></rss>"
    ).encode()


PARSERS: list[tuple[Callable[[bytes], object], type[Exception], bytes]] = [
    (parse_arxiv_atom, AcademicContractError, atom(entry(), 1, 0, 1)),
    (parse_trailofbits_rss, FeedParseError, rss(item())),
]


@pytest.fixture(autouse=True)
def forbid_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*args: object, **kwargs: object) -> None:
        raise AssertionError("independent offline parser tests must not use network")

    monkeypatch.setattr(socket, "socket", fail)
    monkeypatch.setattr(socket, "create_connection", fail)
    monkeypatch.setattr(socket, "getaddrinfo", fail)


@pytest.mark.parametrize("parser,error,valid", PARSERS, ids=["atom", "rss"])
@pytest.mark.parametrize(
    "prefix",
    [
        b'<!DOCTYPE feed [<!ENTITY x SYSTEM "https://outside.invalid/">]>',
        b'<!DOCTYPE feed [<!ENTITY % x SYSTEM "file:///private">%x;]>',
        b'<!DOCTYPE feed [<!ENTITY a "foo"><!ENTITY b "&a;&a;">]>',
        b'<!DOCTYPE feed PUBLIC "external" "https://outside.invalid/">',
    ],
    ids=["external-entity", "parameter-entity", "internal-expansion", "public-dtd"],
)
def test_dtd_is_rejected_before_any_network(
    parser: Callable[[bytes], object], error: type[Exception], valid: bytes, prefix: bytes
) -> None:
    with pytest.raises(error):
        parser(prefix + valid)


@pytest.mark.parametrize("parser,error,valid", PARSERS, ids=["atom", "rss"])
@pytest.mark.parametrize("encoding", ["utf-16", "utf-32", "latin-1"])
def test_unsupported_wire_encoding_is_rejected(
    parser: Callable[[bytes], object], error: type[Exception], valid: bytes, encoding: str
) -> None:
    declaration = f'<?xml version="1.0" encoding="{encoding}"?>'
    with pytest.raises(error):
        parser((declaration + valid.decode()).encode(encoding))


@pytest.mark.parametrize("parser,error,valid", PARSERS, ids=["atom", "rss"])
@pytest.mark.parametrize("invalid", [b"", b"\xff", b" " * 2097153], ids=["empty", "utf8", "bytes"])
def test_byte_inputs_fail_with_domain_error(
    parser: Callable[[bytes], object], error: type[Exception], valid: bytes, invalid: bytes
) -> None:
    with pytest.raises(error):
        parser(invalid)


@pytest.mark.parametrize("parser,error,valid", PARSERS, ids=["atom", "rss"])
def test_bom_and_exact_byte_limit_are_accepted(
    parser: Callable[[bytes], object], error: type[Exception], valid: bytes
) -> None:
    assert parser(b"\xef\xbb\xbf" + valid) == parser(valid)
    assert parser(valid + b" " * (2097152 - len(valid))) == parser(valid)


def test_atom_exact_node_limit_then_one_more_node() -> None:
    valid = atom("<x/>" * 9996)
    assert parse_arxiv_atom(valid).records == ()
    with pytest.raises(AcademicContractError):
        parse_arxiv_atom(atom("<x/>" * 9997))


def test_rss_exact_node_limit_then_one_more_node() -> None:
    assert parse_trailofbits_rss(rss("<x/>" * 9997)) == ()
    with pytest.raises(FeedParseError):
        parse_trailofbits_rss(rss("<x/>" * 9998))


def test_atom_exact_depth_limit_then_one_more_level() -> None:
    assert parse_arxiv_atom(atom("<x>" * 31 + "</x>" * 31)).records == ()
    with pytest.raises(AcademicContractError):
        parse_arxiv_atom(atom("<x>" * 32 + "</x>" * 32))


def test_rss_exact_depth_limit_then_one_more_level() -> None:
    assert parse_trailofbits_rss(rss("<x>" * 30 + "</x>" * 30)) == ()
    with pytest.raises(FeedParseError):
        parse_trailofbits_rss(rss("<x>" * 31 + "</x>" * 31))


def test_atom_exact_entry_limit_and_immutable_output() -> None:
    records = "".join(entry(f"2610.{number:05d}v1") for number in range(1000))
    page = parse_arxiv_atom(atom(records, 1000, 0, 1000))
    assert len(page.records) == 1000
    assert isinstance(page.records, tuple)
    field_name = "start_index"
    with pytest.raises(FrozenInstanceError):
        setattr(page, field_name, 1)
    with pytest.raises(AcademicContractError):
        parse_arxiv_atom(atom(records + entry("2610.10000v1"), 1001, 0, 1001))


def test_rss_exact_entry_limit_and_no_truncation() -> None:
    records = "".join(
        item(f"https://blog.trailofbits.com/review/{number}/") for number in range(1000)
    )
    parsed = parse_trailofbits_rss(rss(records))
    assert len(parsed) == 1000 and isinstance(parsed, tuple)
    with pytest.raises(FeedParseError):
        parse_trailofbits_rss(rss(records + item()))


@pytest.mark.parametrize("identifier", ["2610.00001", "2610.00001v0", "2610.00001v01"])
def test_unknown_or_invalid_version_is_not_defaulted(identifier: str) -> None:
    with pytest.raises(AcademicContractError):
        parse_arxiv_atom(atom(entry(identifier), 1, 0, 1))


def test_time_and_capability_gaps_stay_unknown() -> None:
    paper = parse_arxiv_atom(atom(entry(), 1, 0, 1)).records[0]
    assert paper.published_at is None and paper.modified_at is None
    assert paper.full_text_link is None and paper.full_text_fetched is False
    assert paper.extraction_status == "metadata_only"
    article = parse_trailofbits_rss(
        rss(
            item(),
        )
    )[0]
    assert article.published_at is None and article.modified_at is None
    assert article.body_text is None
    assert set(article.missing_fields) == {"published", "modified", "body", "article_body"}


def test_rss_build_date_does_not_become_article_modified() -> None:
    payload = rss(item()).replace(
        b"</channel>", b"<lastBuildDate>Thu, 15 Oct 2026 18:00:00 +0000</lastBuildDate></channel>"
    )
    assert parse_trailofbits_rss(payload)[0].modified_at is None


@pytest.mark.parametrize(
    "uri",
    [
        "https://user@blog.trailofbits.com/x",
        "https://blog.trailofbits.com:443/x",
        "https://blog.trailofbits.com.evil.invalid/x",
        "https://blog.trailofbits.com\\evil.invalid/x",
        "javascript:alert(1)",
        "https://blog.trailofbits.com/x&#9;y",
    ],
    ids=["userinfo", "port", "domain-suffix", "backslash", "scheme", "tab"],
)
def test_rss_malicious_article_uri_is_rejected(uri: str) -> None:
    with pytest.raises(FeedParseError):
        parse_trailofbits_rss(rss(item(uri)))


@pytest.mark.parametrize(
    "uri", ["https://user@arxiv.org/pdf/2610.00001v1", "https://arxiv.org/pdf/2610.00001v2"]
)
def test_pdf_origin_and_version_conflict_are_rejected(uri: str) -> None:
    with pytest.raises(AcademicContractError):
        parse_arxiv_atom(atom(entry(extra=f'<link title="pdf" href="{uri}"/>'), 1, 0, 1))


def test_license_identifier_is_not_a_fulltext_grant() -> None:
    identifier = "https://publisher.invalid/unknown"
    paper = parse_arxiv_atom(
        atom(entry(extra=f"<arxiv:license>{identifier}</arxiv:license>"), 1, 0, 1)
    ).records[0]
    assert paper.license_identifier == identifier
    assert paper.full_text_fetched is False and paper.full_text_link is None


def test_feed_only_description_identity_and_revision() -> None:
    base = item(
        extra="<guid>one</guid><description>&lt;script&gt;feed&lt;/script&gt;</description>"
    )
    first = parse_trailofbits_rss(rss(base))[0]
    second = parse_trailofbits_rss(rss(base.replace("one", "two")))[0]
    revised = parse_trailofbits_rss(rss(base.replace("feed", "revised")))[0]
    assert first.source_record_id == second.source_record_id == revised.source_record_id
    assert first.body_text == "<script>feed</script>" and "article_body" in first.missing_fields
    assert first.content_hash_sha256 != revised.content_hash_sha256


def test_atom_underfull_nonfinal_page_is_not_success() -> None:
    with pytest.raises(AcademicContractError):
        parse_arxiv_atom(atom(entry(), total=100, start=0, size=10))


def test_rss_invalid_numeric_timezone_minutes_are_rejected() -> None:
    with pytest.raises(FeedParseError):
        parse_trailofbits_rss(rss(item(extra="<pubDate>Wed, 14 Oct 2026 07:00:00 +1260</pubDate>")))


def test_rss_del_control_character_uri_is_rejected() -> None:
    with pytest.raises(FeedParseError):
        parse_trailofbits_rss(rss(item("https://blog.trailofbits.com/review/&#127;")))


def test_arxiv_del_control_character_license_is_rejected() -> None:
    with pytest.raises(AcademicContractError):
        parse_arxiv_atom(
            atom(
                entry(extra="<arxiv:license>https://publisher.invalid/&#127;</arxiv:license>"),
                1,
                0,
                1,
            )
        )
