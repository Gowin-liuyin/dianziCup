"""AVID schema/date precision and separate advisory references stay conservative."""

import json

import pytest

from ai_intel.ingestion.sources.avid_records import normalize_avid_vulnerability
from ai_intel.ingestion.sources.repository import RepositoryFetchError


def avid_record(**changes: object) -> bytes:
    return json.dumps(
        {
            "data_type": "AVID",
            "data_version": "0.2",
            "metadata": {"vuln_id": "AVID-2023-V001"},
            "problemtype": {"description": {"lang": "eng", "value": "Sample evasion"}},
            "description": {"lang": "eng", "value": "External claims remain source material."},
            "published_date": "2023-03-31",
            "last_modified_date": "2023-03-31",
            "references": [],
            **changes,
        }
    ).encode()


def test_each_advisory_reference_retains_separate_identifier() -> None:
    references = [
        {
            "type": "source",
            "label": "first",
            "url": "https://nvd.nist.gov/vuln/detail/CVE-2023-1234",
        },
        {
            "type": "source",
            "label": "second",
            "url": "https://github.com/advisories/GHSA-fccc-8m69-8r78",
        },
        {"type": "source", "label": "third", "url": "https://avidml.org/database/AVID-2023-V002"},
        {
            "type": "source",
            "label": "duplicate",
            "url": "https://nvd.nist.gov/vuln/detail/CVE-2023-1234",
        },
        {
            "type": "source",
            "label": "CVE-2023-9999 unrelated label",
            "url": "https://example.org/research",
        },
    ]
    article = normalize_avid_vulnerability(avid_record(references=references))
    assert article.article_id == "AVID-2023-V001"
    assert article.referenced_advisory_ids == (
        "CVE-2023-1234",
        "GHSA-fccc-8m69-8r78",
        "AVID-2023-V002",
    )
    assert article.body_text == "External claims remain source material."


def test_replay_stable_id_and_missing_body_stay_unknown() -> None:
    payload = avid_record(description=None, published_date=None, last_modified_date=None)
    first = normalize_avid_vulnerability(payload)
    assert first == normalize_avid_vulnerability(payload)
    assert first.body_text is None
    assert first.referenced_advisory_ids == ()


@pytest.mark.parametrize(
    "changes",
    [
        {"data_version": "0.3"},
        {"data_type": "directory"},
        {"metadata": {"vuln_id": "main"}},
        {"metadata": []},
        {"problemtype": {"description": {"lang": "eng", "value": ""}}},
        {"description": {"lang": "eng", "value": []}},
        {"published_date": "2023-03-31T00:00:00Z"},
        {"last_modified_date": "2023-02-30"},
        {"references": "not-a-list"},
        {"references": [None]},
        {"references": [{"type": "source", "label": 42, "url": "https://example.org"}]},
    ],
)
def test_malformed_or_unknown_avid_fields_fail(changes: dict[str, object]) -> None:
    with pytest.raises(RepositoryFetchError):
        normalize_avid_vulnerability(avid_record(**changes))


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "javascript:alert(1)",
        "https://127.0.0.1/poc",
        "https://10.0.0.1/poc",
        "https://[::1]/poc",
        "https://localhost/poc",
        "https://example.local/poc",
        "https://user:password@example.org/poc",
        "https://example.org:444/poc",
        "https://example.org:invalid/poc",
        "https://example.org/\npoc",
        "https://example.org\\@localhost/poc",
    ],
)
def test_reference_is_public_metadata_and_never_a_fetch_instruction(url: str) -> None:
    with pytest.raises(RepositoryFetchError):
        normalize_avid_vulnerability(
            avid_record(references=[{"type": "source", "label": "PoC", "url": url}])
        )


@pytest.mark.parametrize(
    "payload",
    [
        b"[]",
        b'{"data_type":"AVID","data_type":"AVID"}',
        b'{"unknown":NaN}',
        b'{"unknown":"\\u0000"}',
        b'{"unknown":"\\ud800"}',
        b"{" + b" " * (2 * 1024 * 1024) + b"}",
    ],
    ids=["directory", "duplicate", "nan", "nul", "surrogate", "byte-limit"],
)
def test_hostile_json_rejected(payload: bytes) -> None:
    with pytest.raises(RepositoryFetchError):
        normalize_avid_vulnerability(payload)


def test_reference_limit_and_bad_second_reference_fail_entire_record() -> None:
    good = {"type": "source", "label": "source", "url": "https://example.org/research"}
    for references in ([good] * 129, [good, "not-an-object"]):
        with pytest.raises(RepositoryFetchError):
            normalize_avid_vulnerability(avid_record(references=references))
