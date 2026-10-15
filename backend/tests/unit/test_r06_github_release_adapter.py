"""GitHub release identity, unknown dates and hostile page boundaries."""

import json

import pytest

from ai_intel.ingestion.sources.github_releases import parse_github_releases
from ai_intel.ingestion.sources.repository import RepositoryFetchError


def release_page(**changes: object) -> bytes:
    release = {
        "id": 42,
        "tag_name": "v1.0-rc1",
        "name": "Security release candidate",
        "body": "CVE discussion is not confirmation that this fixes it.",
        "draft": False,
        "prerelease": True,
        "target_commitish": "main",
        "html_url": "https://github.com/ollama/ollama/releases/tag/v1.0-rc1",
        "published_at": "2026-10-14T19:45:22Z",
        **changes,
    }
    return json.dumps([release]).encode()


def test_stable_numeric_release_id_does_not_become_commit_or_advisory() -> None:
    record = parse_github_releases(release_page())[0]
    assert record.record_type == "release"
    assert record.fixed_identifier == "github:ollama/ollama:release:42"
    assert record.related_product == "ollama"
    assert record.published_at == "2026-10-14T19:45:22Z"
    assert record.metadata_only_link is None
    changed_tag = parse_github_releases(release_page(tag_name="v1.0", name="Retitled"))[0]
    assert changed_tag.fixed_identifier == record.fixed_identifier
    assert record.fixed_identifier != "main"


def test_empty_page_and_missing_publication_preserve_unknown() -> None:
    assert parse_github_releases(b"[]") == ()
    record = parse_github_releases(release_page(published_at=None, name=None, draft=True))[0]
    assert record.published_at is None
    assert record.title == "v1.0-rc1"


@pytest.mark.parametrize(
    "changes",
    [
        {"id": True},
        {"id": -1},
        {"id": "42"},
        {"tag_name": ""},
        {"name": {}},
        {"body": []},
        {"draft": "false"},
        {"prerelease": None},
        {"target_commitish": []},
        {"published_at": "2026-10-14T19:45:22"},
        {"published_at": 42},
        {"html_url": "https://github.com/other/repository/releases/tag/v1"},
        {"html_url": "https://github.com@localhost/ollama/ollama/releases/tag/v1"},
        {"html_url": "http://github.com/ollama/ollama/releases/tag/v1"},
        {"html_url": "https://github.com/ollama/ollama/releases/tag/v1?token=not-read"},
    ],
)
def test_bad_release_entry_is_explicit_page_failure(changes: dict[str, object]) -> None:
    with pytest.raises(RepositoryFetchError):
        parse_github_releases(release_page(**changes))


@pytest.mark.parametrize(
    "payload",
    [
        b"{}",
        b"null",
        b"[false]",
        b'[{"id":42,"id":43}]',
        b'[{"unused":NaN}]',
        b'[{"unused":1e9999}]',
        b'[{"unused":"\\u0000"}]',
        b'[{"unused":"\\ud800"}]',
        b"[]" + b" " * (2 * 1024 * 1024),
        b"[" * 40 + b"0" + b"]" * 40,
        b"[" + b",".join([b"null"] * 10001) + b"]",
        b'[],"injected":[]',
    ],
    ids=[
        "object",
        "null",
        "bad-entry",
        "duplicate",
        "nan",
        "overflow",
        "nul",
        "surrogate",
        "byte-limit",
        "depth-limit",
        "node-limit",
        "wrapper-injection",
    ],
)
def test_invalid_json_structure_and_limits_rejected(payload: bytes) -> None:
    with pytest.raises(RepositoryFetchError):
        parse_github_releases(payload)


def test_invalid_second_record_is_not_silently_skipped() -> None:
    valid = json.loads(release_page())[0]
    for invalid in (False, {**valid, "id": 42}, {**valid, "id": 43, "draft": "false"}):
        with pytest.raises(RepositoryFetchError):
            parse_github_releases(json.dumps([valid, invalid]).encode())


def test_page_record_count_limit_is_independent_of_byte_limit() -> None:
    valid = json.loads(release_page())[0]
    with pytest.raises(RepositoryFetchError, match="record limit"):
        parse_github_releases(
            json.dumps([{**valid, "id": index} for index in range(1, 102)]).encode()
        )
