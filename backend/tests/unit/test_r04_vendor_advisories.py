"""Recorded-source normalization and explicit malformed-input boundaries."""

import copy
import hashlib
import json
from pathlib import Path

import pytest

from ai_intel.ingestion.sources.vendor_advisories import (
    VendorAdvisoryError,
    normalize_vendor_advisory,
)

REPOSITORY = "vllm-project/vllm"
GHSA_ID = "GHSA-6cxc-2vcg-w5qc"
CANONICAL_URI = f"https://github.com/{REPOSITORY}/security/advisories/{GHSA_ID}"


@pytest.fixture
def advisory_payload() -> dict[str, object]:
    return {
        "ghsa_id": GHSA_ID,
        "cve_id": None,
        "html_url": CANONICAL_URI,
        "summary": "Synthetic vendor advisory with explicit version conditions",
        "description": "A package function can retain stale state.",
        "published_at": "2026-10-06T20:45:08Z",
        "updated_at": "2026-10-06T20:45:08Z",
        "withdrawn_at": None,
        "state": "published",
        "vulnerabilities": [
            {
                "package": {"ecosystem": "pip", "name": "vllm"},
                "vulnerable_version_range": "< 0.31.0",
                "patched_versions": ">= 0.31.0",
                "vulnerable_functions": ["InputBatch.condense"],
            }
        ],
    }


def test_recorded_public_non_cve_advisory_preserves_original_conditions() -> None:
    fixture = (
        Path(__file__).resolve().parents[3] / "fixtures/recorded/vllm_vendor_20261015_public.json"
    )
    body = fixture.read_bytes()
    provenance = json.loads(fixture.with_suffix(".provenance.json").read_bytes())
    assert len(body) == 8800
    assert hashlib.sha256(body).hexdigest() == (
        "f084ddcb1eecd43494ac0244dd3b650431727add18deb330bc3df1722912cedf"
    )
    assert provenance["is_synthetic"] is False
    assert provenance["body_sha256"] == hashlib.sha256(body).hexdigest()
    result = normalize_vendor_advisory(json.loads(body)[0], repository=REPOSITORY)
    assert result.ghsa_id == GHSA_ID
    assert result.cve_id is None
    assert result.canonical_uri == CANONICAL_URI
    assert result.product == "vllm"
    assert result.title == (
        "V1 InputBatch.condense leaves a stale allowed_token_ids mask on recycled batch rows"
    )
    assert result.description is not None
    assert "allowed_token_ids" in result.description
    assert result.published_at == "2026-10-06T20:45:08+00:00"
    assert result.updated_at == "2026-10-06T20:45:08+00:00"
    assert result.withdrawn_at is None
    assert result.source_schema_version == "github-repository-advisory:1"
    assert len(result.vulnerabilities) == 1
    package = result.vulnerabilities[0]
    assert package.package_ecosystem == "pip"
    assert package.package_name == "vllm"
    assert package.affected_range == "< 0.31.0"
    assert package.patched_version == ">= 0.31.0"
    assert package.vulnerable_functions == ()


def test_later_cve_assignment_preserves_vendor_identifier_and_uri(
    advisory_payload: dict[str, object],
) -> None:
    initial = normalize_vendor_advisory(advisory_payload, repository=REPOSITORY)
    advisory_payload["cve_id"] = "CVE-2026-12345"
    subsequent = normalize_vendor_advisory(advisory_payload, repository=REPOSITORY)
    assert subsequent.ghsa_id == initial.ghsa_id
    assert subsequent.canonical_uri == initial.canonical_uri
    assert subsequent.cve_id == "CVE-2026-12345"


@pytest.mark.parametrize(
    "field", ["description", "published_at", "updated_at", "withdrawn_at", "cve_id"]
)
def test_optional_null_is_missing_not_fabricated(
    advisory_payload: dict[str, object], field: str
) -> None:
    advisory_payload[field] = None
    result = normalize_vendor_advisory(advisory_payload, repository=REPOSITORY)
    assert getattr(result, field) is None


def test_withdrawal_is_retained_without_losing_historical_description(
    advisory_payload: dict[str, object],
) -> None:
    advisory_payload["withdrawn_at"] = "2026-10-07T04:45:08+08:00"
    result = normalize_vendor_advisory(advisory_payload, repository=REPOSITORY)
    assert result.withdrawn_at == "2026-10-06T20:45:08+00:00"
    assert result.description == "A package function can retain stale state."
    assert result.ghsa_id == GHSA_ID


def test_multiple_packages_and_function_conditions_remain_separate(
    advisory_payload: dict[str, object],
) -> None:
    advisory_payload["vulnerabilities"] = [
        {
            "package": {"ecosystem": "pip", "name": "vllm"},
            "vulnerable_version_range": "< 0.31.0",
            "patched_versions": ">= 0.31.0",
            "vulnerable_functions": ["InputBatch.condense", "InputBatch.add_request"],
        },
        {
            "package": {"ecosystem": "npm", "name": "@example/synthetic-test-client"},
            "vulnerable_version_range": ">= 1.0, < 2.0 || >= 3.0, < 3.1",
            "patched_versions": "2.0, >= 3.1",
            "vulnerable_functions": ["processInput"],
        },
    ]
    result = normalize_vendor_advisory(advisory_payload, repository=REPOSITORY)
    assert len(result.vulnerabilities) == 2
    assert result.vulnerabilities[0].vulnerable_functions == (
        "InputBatch.condense",
        "InputBatch.add_request",
    )
    assert result.vulnerabilities[1].package_ecosystem == "npm"
    assert result.vulnerabilities[1].package_name == "@example/synthetic-test-client"
    assert result.vulnerabilities[1].affected_range == ">= 1.0, < 2.0 || >= 3.0, < 3.1"
    assert result.vulnerabilities[1].patched_version == "2.0, >= 3.1"


@pytest.mark.parametrize("package", [None, {}, {"ecosystem": None, "name": None}])
def test_missing_package_and_versions_remain_unknown(
    advisory_payload: dict[str, object], package: object
) -> None:
    advisory_payload["vulnerabilities"] = [{"package": package}]
    result = normalize_vendor_advisory(advisory_payload, repository=REPOSITORY)
    assert len(result.vulnerabilities) == 1
    vulnerability = result.vulnerabilities[0]
    assert vulnerability.package_ecosystem is None
    assert vulnerability.package_name is None
    assert vulnerability.affected_range is None
    assert vulnerability.patched_version is None
    assert vulnerability.vulnerable_functions == ()


@pytest.mark.parametrize(
    "uri",
    [
        "https://github.com.evil.example/vllm-project/vllm/security/advisories/" + GHSA_ID,
        "https://github.com@evil.example/vllm-project/vllm/security/advisories/" + GHSA_ID,
        "https://user:password@github.com/vllm-project/vllm/security/advisories/" + GHSA_ID,
        "http://github.com/vllm-project/vllm/security/advisories/" + GHSA_ID,
        "https://github.com:443/vllm-project/vllm/security/advisories/" + GHSA_ID,
        "https://github.com/other-owner/vllm/security/advisories/" + GHSA_ID,
        CANONICAL_URI + "?redirect=https://evil.example",
        CANONICAL_URI + "#injected-fragment",
        CANONICAL_URI + "/../GHSA-2345-6789-cfgh",
        CANONICAL_URI.replace("/vllm/", "/%76llm/"),
        CANONICAL_URI + "\n",
    ],
)
def test_noncanonical_or_malicious_source_uri_is_rejected(
    advisory_payload: dict[str, object], uri: str
) -> None:
    advisory_payload["html_url"] = uri
    with pytest.raises(VendorAdvisoryError, match="canonical URI"):
        normalize_vendor_advisory(advisory_payload, repository=REPOSITORY)


@pytest.mark.parametrize(
    "repository", ["other/vllm", "vllm-project/other", "", "VLLM-PROJECT/VLLM"]
)
def test_unapproved_repository_is_rejected(
    advisory_payload: dict[str, object], repository: str
) -> None:
    with pytest.raises(VendorAdvisoryError, match="repository"):
        normalize_vendor_advisory(advisory_payload, repository=repository)


@pytest.mark.parametrize(
    "identifier", ["", "GHSA-abcd-1234-efgh", "ghsa-6cxc-2vcg-w5qc", "GHSA-６cxc-2vcg-w5qc", 42]
)
def test_invalid_ghsa_identifiers_fail_explicitly(
    advisory_payload: dict[str, object], identifier: object
) -> None:
    advisory_payload["ghsa_id"] = identifier
    with pytest.raises(VendorAdvisoryError, match="GHSA"):
        normalize_vendor_advisory(advisory_payload, repository=REPOSITORY)


@pytest.mark.parametrize(
    "identifier", ["", "CVE-2026-123", "CVE-２０２６-12345", "cve-2026-12345", 3]
)
def test_invalid_cve_is_not_silently_dropped(
    advisory_payload: dict[str, object], identifier: object
) -> None:
    advisory_payload["cve_id"] = identifier
    with pytest.raises(VendorAdvisoryError, match="CVE"):
        normalize_vendor_advisory(advisory_payload, repository=REPOSITORY)


@pytest.mark.parametrize("field", ["published_at", "updated_at", "withdrawn_at"])
@pytest.mark.parametrize(
    "timestamp", ["2026-10-06T20:45:08", "2026-10-06 20:45:08Z", "2026-02-30T00:00:00Z", 42]
)
def test_non_rfc3339_or_unzoned_time_is_rejected_without_guessing(
    advisory_payload: dict[str, object], field: str, timestamp: object
) -> None:
    advisory_payload[field] = timestamp
    with pytest.raises(VendorAdvisoryError, match="timestamp"):
        normalize_vendor_advisory(advisory_payload, repository=REPOSITORY)


@pytest.mark.parametrize("field", ["summary", "description"])
@pytest.mark.parametrize("value", ["invalid\x00text", "invalid\ud800text", 123, ""])
def test_invalid_text_is_not_persisted_as_success(
    advisory_payload: dict[str, object], field: str, value: object
) -> None:
    advisory_payload[field] = value
    with pytest.raises(VendorAdvisoryError):
        normalize_vendor_advisory(advisory_payload, repository=REPOSITORY)


@pytest.mark.parametrize("vulnerabilities", [None, {}, "not-an-array", [None], ["package"]])
def test_malformed_vulnerabilities_do_not_become_an_empty_success(
    advisory_payload: dict[str, object], vulnerabilities: object
) -> None:
    advisory_payload["vulnerabilities"] = vulnerabilities
    with pytest.raises(VendorAdvisoryError, match="vulnerabilit"):
        normalize_vendor_advisory(advisory_payload, repository=REPOSITORY)


@pytest.mark.parametrize("field", ["vulnerable_version_range", "patched_versions", "package"])
def test_malformed_package_conditions_fail_instead_of_disappearing(
    advisory_payload: dict[str, object], field: str
) -> None:
    advisory_payload["vulnerabilities"] = [{field: 123}]
    with pytest.raises(VendorAdvisoryError):
        normalize_vendor_advisory(advisory_payload, repository=REPOSITORY)


@pytest.mark.parametrize("functions", ["condense", [123], ["bad\x00name"], ["bad\ud800name"]])
def test_malformed_function_conditions_are_rejected(
    advisory_payload: dict[str, object], functions: object
) -> None:
    advisory_payload["vulnerabilities"] = [{"vulnerable_functions": functions}]
    with pytest.raises(VendorAdvisoryError):
        normalize_vendor_advisory(advisory_payload, repository=REPOSITORY)


@pytest.mark.parametrize("state", ["draft", "closed", "triage", None])
def test_nonpublic_advisory_is_not_normalized_as_public(
    advisory_payload: dict[str, object], state: object
) -> None:
    advisory_payload["state"] = state
    with pytest.raises(VendorAdvisoryError, match="published"):
        normalize_vendor_advisory(advisory_payload, repository=REPOSITORY)


def test_normalization_does_not_mutate_raw_payload(advisory_payload: dict[str, object]) -> None:
    original = copy.deepcopy(advisory_payload)
    normalize_vendor_advisory(advisory_payload, repository=REPOSITORY)
    assert advisory_payload == original


def test_empty_vulnerabilities_are_explicitly_retained(advisory_payload: dict[str, object]) -> None:
    advisory_payload["vulnerabilities"] = []
    result = normalize_vendor_advisory(advisory_payload, repository=REPOSITORY)
    assert result.vulnerabilities == ()


def test_unicode_description_preserves_exact_source_text(
    advisory_payload: dict[str, object],
) -> None:
    description = '中文说明🙂\nInputBatch.condense 的 "mask" 条件与 \\ 路径原文。'
    advisory_payload["description"] = description
    assert (
        normalize_vendor_advisory(advisory_payload, repository=REPOSITORY).description
        == description
    )


@pytest.mark.parametrize(
    "timestamp",
    [
        "2026-10-06T20:45:08-00:00",
        "2026-10-06T20:45:08+00:60",
        "2026-10-06T20:45:08+24:00",
        "2026-10-06T20:45:08.1234567Z",
    ],
)
def test_unknown_offset_and_lossy_or_invalid_times_are_rejected(
    advisory_payload: dict[str, object], timestamp: str
) -> None:
    advisory_payload["published_at"] = timestamp
    with pytest.raises(VendorAdvisoryError, match="timestamp"):
        normalize_vendor_advisory(advisory_payload, repository=REPOSITORY)


def test_offset_and_microseconds_normalize_to_utc_without_truncation(
    advisory_payload: dict[str, object],
) -> None:
    advisory_payload["published_at"] = "2026-10-07T04:45:08.123456+08:00"
    result = normalize_vendor_advisory(advisory_payload, repository=REPOSITORY)
    assert result.published_at == "2026-10-06T20:45:08.123456+00:00"


@pytest.mark.parametrize("field", ["description", "summary"])
def test_oversized_source_text_is_rejected(advisory_payload: dict[str, object], field: str) -> None:
    advisory_payload[field] = "x" * 1_000_001
    with pytest.raises(VendorAdvisoryError, match="text"):
        normalize_vendor_advisory(advisory_payload, repository=REPOSITORY)


def test_utf8_total_text_budget_is_not_a_character_budget(
    advisory_payload: dict[str, object],
) -> None:
    advisory_payload["description"] = "中" * 333_334
    with pytest.raises(VendorAdvisoryError, match="text budget"):
        normalize_vendor_advisory(advisory_payload, repository=REPOSITORY)


def test_excessive_package_count_is_rejected(advisory_payload: dict[str, object]) -> None:
    advisory_payload["vulnerabilities"] = [{}] * 257
    with pytest.raises(VendorAdvisoryError, match="vulnerabilities"):
        normalize_vendor_advisory(advisory_payload, repository=REPOSITORY)


@pytest.mark.parametrize("functions", [[None], ["x"] * 257, ["x" * 1001]])
def test_missing_or_excessive_function_conditions_are_rejected(
    advisory_payload: dict[str, object], functions: object
) -> None:
    advisory_payload["vulnerabilities"] = [{"vulnerable_functions": functions}]
    with pytest.raises(VendorAdvisoryError):
        normalize_vendor_advisory(advisory_payload, repository=REPOSITORY)


@pytest.mark.parametrize("package", [{"ecosystem": 42}, {"name": "bad\x00name"}])
def test_invalid_package_text_is_rejected(
    advisory_payload: dict[str, object], package: object
) -> None:
    advisory_payload["vulnerabilities"] = [{"package": package}]
    with pytest.raises(VendorAdvisoryError):
        normalize_vendor_advisory(advisory_payload, repository=REPOSITORY)


def test_missing_required_summary_is_rejected(advisory_payload: dict[str, object]) -> None:
    del advisory_payload["summary"]
    with pytest.raises(VendorAdvisoryError, match="missing summary"):
        normalize_vendor_advisory(advisory_payload, repository=REPOSITORY)
