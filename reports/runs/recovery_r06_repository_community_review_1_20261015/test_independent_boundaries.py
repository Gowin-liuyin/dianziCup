"""Independent parser checks; expected results come from source fields and strict types."""

import json
from pathlib import Path

import pytest
from ai_intel.ingestion.sources.avid_records import normalize_avid_vulnerability
from ai_intel.ingestion.sources.github_releases import parse_github_releases
from ai_intel.ingestion.sources.osv import (
    OsvContractError,
    bounded_package_query,
    normalize_osv_record,
)
from ai_intel.ingestion.sources.repository import RepositoryFetchError

AUTHOR_RUN = (
    Path(__file__).resolve().parents[1] / "recovery_r06_repository_community_20261015"
)


@pytest.mark.parametrize(
    "fields",
    [
        {"aliases": None},
        {"related": None},
        {"upstream": None},
        {"affected": None},
        {"affected": [{"ranges": None}]},
        {"affected": [{"ranges": [{"type": "SEMVER", "events": None}]}]},
        {"affected": [{"versions": None}]},
    ],
    ids=[
        "aliases-null",
        "related-null",
        "upstream-null",
        "affected-null",
        "ranges-null",
        "events-null",
        "versions-null",
    ],
)
def test_present_null_array_is_not_missing_or_success(
    fields: dict[str, object],
) -> None:
    with pytest.raises(OsvContractError):
        normalize_osv_record({"id": "OSV-REVIEW", **fields})


def test_same_type_ranges_and_repositories_stay_separate() -> None:
    payload = {
        "id": "OSV-REVIEW",
        "schema_version": "1.999.7",
        "modified": "2026-10-15T01:02:03.123456789Z",
        "unknown_extension": {"leave": ["intact", 9]},
        "affected": [
            {
                "package": {"ecosystem": "FutureEcosystem", "name": "example"},
                "ranges": [
                    {
                        "type": "GIT",
                        "repo": "https://github.com/one/repo",
                        "events": [{"introduced": "0"}, {"fixed": "a" * 40}],
                    },
                    {
                        "type": "GIT",
                        "repo": "https://github.com/two/repo",
                        "events": [
                            {"introduced": "b" * 40},
                            {"last_affected": "c" * 40},
                        ],
                    },
                    {
                        "type": "FUTURE",
                        "repo": "https://github.com/three/repo",
                        "events": [{"future_boundary": "x"}],
                    },
                ],
            }
        ],
    }
    record = normalize_osv_record(payload)
    branches = record.affected[0].range_branches
    assert tuple(branch.repository_uri for branch in branches) == (
        "https://github.com/one/repo",
        "https://github.com/two/repo",
        "https://github.com/three/repo",
    )
    assert branches[0].events[1].version_value == "a" * 40
    assert branches[1].events[0].version_value == "b" * 40
    assert branches[2].unsupported_scheme is True
    assert record.modified_at == "2026-10-15T01:02:03.123456789Z"
    assert record.raw_record == payload


@pytest.mark.parametrize("version", ["2.0.0", "1.2", "1.09.2", "1.9.2-beta", 1])
def test_unknown_or_malformed_schema_is_explicit(version: object) -> None:
    with pytest.raises(OsvContractError):
        normalize_osv_record({"id": "OSV-REVIEW", "schema_version": version})


@pytest.mark.parametrize(
    "records",
    [[{"id": "x"}, None], [False], [{"id": "x"}] * 1001],
    ids=["bad-second", "bad-first", "count-limit"],
)
def test_query_keeps_bad_record_failure_visible(records: list[object]) -> None:
    with pytest.raises(OsvContractError):
        bounded_package_query(lambda ecosystem, package: records, "Go", "example")


def test_release_flags_and_body_are_source_facts_and_main_is_not_sha() -> None:
    raw = json.loads((AUTHOR_RUN / "ollama_release_real.body").read_bytes())
    first = raw[0]
    assert first["id"] == 413093320
    assert first["tag_name"] == "v0.40.5-rc0"
    assert first["name"] == "v0.40.5"
    assert first["draft"] is False and first["prerelease"] is True
    assert first["target_commitish"] == "main"
    assert isinstance(first["body"], str) and first["body"]
    before = parse_github_releases(json.dumps(raw).encode())[0]
    after = parse_github_releases(
        json.dumps([{**first, "name": "Changed", "tag_name": "other"}]).encode()
    )[0]
    assert (
        before.fixed_identifier
        == after.fixed_identifier
        == "github:ollama/ollama:release:413093320"
    )
    assert before.record_type == "release"
    assert before.metadata_only_link is None


@pytest.mark.parametrize("field", ["draft", "prerelease", "body"])
def test_release_flags_and_body_bad_types_rejected(field: str) -> None:
    raw = json.loads((AUTHOR_RUN / "ollama_release_real.body").read_bytes())
    raw[0][field] = ["bad-type"]
    with pytest.raises(RepositoryFetchError):
        parse_github_releases(json.dumps(raw).encode())


@pytest.mark.parametrize("index", [2, 3])
def test_avid_date_only_and_original_references_remain_in_raw(index: int) -> None:
    raw = (AUTHOR_RUN / f"avid_{index:02}.record.json").read_bytes()
    document = json.loads(raw)
    assert document["data_type"] == "AVID" and document["data_version"] == "0.2"
    assert document["published_date"] == document["last_modified_date"] == "2023-03-31"
    assert document["references"]
    article = normalize_avid_vulnerability(raw)
    assert article.article_id == document["metadata"]["vuln_id"]
    assert article.title == document["problemtype"]["description"]["value"]
    assert article.body_text == document["description"]["value"]
    assert article.referenced_advisory_ids == ()
    assert b"2023-03-31T00:00" not in raw


@pytest.mark.parametrize(
    "change",
    [
        {"data_version": "1.0"},
        {"published_date": "2023-02-29"},
        {"references": [{"type": "source", "label": "PoC", "url": "https://[::1]/x"}]},
    ],
)
def test_avid_unconfirmed_schema_and_bad_metadata_rejected(
    change: dict[str, object],
) -> None:
    document = json.loads((AUTHOR_RUN / "avid_02.record.json").read_bytes())
    with pytest.raises(RepositoryFetchError):
        normalize_avid_vulnerability(json.dumps({**document, **change}).encode())
