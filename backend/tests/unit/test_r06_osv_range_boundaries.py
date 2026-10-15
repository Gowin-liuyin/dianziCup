"""OSV range branches and malformed typed fields stay observable."""

import pytest

from ai_intel.ingestion.sources.osv import (
    OsvContractError,
    bounded_package_query,
    normalize_osv_record,
)


def test_multiple_range_types_keep_independent_boundaries() -> None:
    payload = {
        "id": "OSV-EXAMPLE",
        "affected": [
            {
                "package": {"ecosystem": "FutureEcosystem", "name": "example"},
                "ranges": [
                    {"type": "SEMVER", "events": [{"introduced": "0"}, {"fixed": "1.2"}]},
                    {
                        "type": "GIT",
                        "repo": "https://github.com/example/example",
                        "events": [{"introduced": "a" * 40}, {"last_affected": "b" * 40}],
                    },
                ],
                "versions": ["0.1", "1.1"],
            }
        ],
    }
    record = normalize_osv_record(payload)
    package = record.affected[0]
    assert package.ecosystem == "FutureEcosystem"
    assert len(package.range_branches) == 2
    assert [branch.range_type for branch in package.range_branches] == ["SEMVER", "GIT"]
    assert package.range_branches[0].events[1].version_value == "1.2"
    assert package.range_branches[1].repository_uri == "https://github.com/example/example"
    assert package.range_branches[1].events[1].event_type == "last_affected"
    assert len(package.events) == 4
    assert package.ranges_type == "GIT"
    assert package.explicit_versions == ("0.1", "1.1")
    assert record.raw_record == payload


@pytest.mark.parametrize(
    "invalid_fields",
    [
        {"aliases": "CVE-1"},
        {"aliases": ["CVE-1", 3]},
        {"modified": {"unexpected": "date"}},
        {"withdrawn": False},
        {"schema_version": "2.0.0"},
        {"affected": "not-an-array"},
        {"affected": [{"package": {"ecosystem": 4}}]},
        {"affected": [{"ranges": "not-an-array"}]},
        {"affected": [{"ranges": [{"type": "SEMVER", "events": [{"fixed": 4}]}]}]},
        {"affected": [{"versions": ["1.0", False]}]},
    ],
)
def test_malformed_osv_fields_fail_without_coercing_or_skipping(
    invalid_fields: dict[str, object],
) -> None:
    with pytest.raises(OsvContractError):
        normalize_osv_record({"id": "OSV-EXAMPLE", **invalid_fields})


def test_limit_and_unknown_boundary_are_retained_without_interpretation() -> None:
    record = normalize_osv_record(
        {
            "id": "OSV-EXAMPLE",
            "schema_version": "1.9.2",
            "affected": [
                {
                    "ranges": [
                        {"type": "ECOSYSTEM", "events": [{"introduced": "0"}, {"limit": "9"}]},
                        {"type": "FUTURE", "events": [{"future_boundary": "branch-2"}]},
                    ]
                }
            ],
        }
    )
    assert record.affected[0].range_branches[0].unsupported_scheme is False
    assert record.affected[0].range_branches[1].unsupported_scheme is True
    assert record.affected[0].unsupported_scheme is True
    assert record.affected[0].range_branches[0].events[1].event_type == "limit"


def test_nan_and_nul_are_not_valid_normalized_osv_values() -> None:
    for payload in ({"id": "OSV-EXAMPLE", "unexpected": float("nan")}, {"id": "OSV-\0"}):
        with pytest.raises(OsvContractError):
            normalize_osv_record(payload)


def test_bounded_query_does_not_skip_a_bad_second_record() -> None:
    with pytest.raises(OsvContractError):
        bounded_package_query(
            lambda ecosystem, package: [{"id": "OSV-EXAMPLE"}, None], "Go", "example"
        )
