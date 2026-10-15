"""Untrusted branch keywords and bypassed source values cannot prove version exclusion."""

from __future__ import annotations

import pytest

from ai_intel.assessment.version_ranges import contains_version, evaluate_version_assertion
from ai_intel.domain.enrichment_values import VersionAssertionValue, VersionInterval

INVALID_BRANCHES = (
    "",
    " ",
    " stable",
    "stable ",
    "stable\x00",
    "stable\nbranch",
    "stable\x7fbranch",
    "stable\x81branch",
    "stable\u200bbranch",
    "b" * 201,
    1,
    True,
)


def source_with_interval(interval: VersionInterval) -> VersionAssertionValue:
    return VersionAssertionValue(
        package_key="pkg:pypi/fixture-package",
        ecosystem="PyPI",
        scheme="pep440",
        raw_expression="synthetic branch context",
        intervals=(interval,),
        comparison_support="supported",
    )


@pytest.mark.parametrize("branch", INVALID_BRANCHES)
def test_contains_rejects_invalid_asset_branch_context(branch: str | None) -> None:
    result = contains_version(
        "1.5",
        VersionInterval(introduced="1", fixed="2", branch="stable"),
        scheme="pep440",
        ecosystem="PyPI",
        branch=branch,
    )
    assert (result.status, result.reason) == ("unknown", "invalid_asset_branch")


@pytest.mark.parametrize("branch", INVALID_BRANCHES)
def test_contains_rejects_invalid_source_branch_context(branch: str | None) -> None:
    interval = VersionInterval(introduced="1", fixed="2", branch="stable").model_copy(
        update={"branch": branch}
    )
    result = contains_version("1.5", interval, scheme="pep440", ecosystem="PyPI", branch="stable")
    assert (result.status, result.reason) == ("unknown", "invalid_source_branch")


@pytest.mark.parametrize("branch", INVALID_BRANCHES)
@pytest.mark.parametrize("explicit_or_excluded", ["explicit", "excluded"])
def test_invalid_asset_branch_stays_unknown_even_with_precise_version_evidence(
    branch: str | None, explicit_or_excluded: str
) -> None:
    source = source_with_interval(VersionInterval(introduced="1", fixed="2", branch="stable"))
    if explicit_or_excluded == "explicit":
        source = source.model_copy(update={"explicit_versions": ("1.5",)})
    result = evaluate_version_assertion(
        source,
        package_key=source.package_key,
        ecosystem=source.ecosystem,
        version="1.5",
        version_scheme=source.scheme,
        branch=branch,
        excluded_versions=("1.5",) if explicit_or_excluded == "excluded" else (),
        range_complete=True,
    )
    assert (result.status, result.reason) == ("unknown", "invalid_asset_branch")
    assert result.interval_results[0].status == "unknown"
    assert "invalid_asset_branch" in result.unresolved_reasons


@pytest.mark.parametrize("branch", INVALID_BRANCHES)
def test_invalid_source_branch_is_retained_in_assertion_audit(branch: str | None) -> None:
    interval = VersionInterval(introduced="1", fixed="2", branch="stable").model_copy(
        update={"branch": branch}
    )
    source = source_with_interval(interval)
    result = evaluate_version_assertion(
        source,
        package_key=source.package_key,
        ecosystem=source.ecosystem,
        version="1.5",
        version_scheme=source.scheme,
        branch="stable",
        range_complete=True,
    )
    assert result.status == "unknown"
    assert result.interval_results[0].reason == "invalid_source_branch"
    assert result.unresolved_reasons == ("invalid_source_branch",)


@pytest.mark.parametrize(
    "asset_branch,source_branch,status,reason",
    [
        (None, "stable", "unknown", "missing_branch"),
        ("stable", "stable", "affected", "inside_interval"),
        ("preview", "stable", "not_affected", "branch_mismatch"),
        ("b" * 200, "b" * 200, "affected", "inside_interval"),
        ("稳定版本", "稳定版本", "affected", "inside_interval"),
        ("stable release", "stable release", "affected", "inside_interval"),
    ],
)
def test_legal_exact_branch_context_preserves_previous_semantics(
    asset_branch: str | None, source_branch: str, status: str, reason: str
) -> None:
    interval = VersionInterval(introduced="1", fixed="2", branch=source_branch)
    result = contains_version(
        "1.5", interval, scheme="pep440", ecosystem="PyPI", branch=asset_branch
    )
    assert (result.status, result.reason) == (status, reason)


def test_exclusion_preserves_all_existing_unresolved_source_reasons() -> None:
    source = source_with_interval(VersionInterval(introduced="1", fixed="2", branch="stable"))
    source = source.model_copy(update={"explicit_versions": ("invalid",)})
    before = source.model_dump_json()
    result = evaluate_version_assertion(
        source,
        package_key=source.package_key,
        ecosystem=source.ecosystem,
        version="1.5",
        version_scheme=source.scheme,
        excluded_versions=("1.5",),
    )
    assert (result.status, result.reason) == ("not_affected", "explicitly_excluded")
    assert result.interval_results[0].reason == "missing_branch"
    assert result.unresolved_reasons == ("missing_branch", "invalid_explicit_version")
    assert source.model_dump_json() == before
