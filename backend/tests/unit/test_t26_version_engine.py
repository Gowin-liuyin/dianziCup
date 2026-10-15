"""Synthetic algorithm cases follow T26 boundaries without asserting live applicability."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

from ai_intel.assessment.version_ranges import (
    compare_versions,
    contains_version,
    evaluate_version_assertion,
)
from ai_intel.domain.enrichment_values import VersionAssertionValue, VersionInterval


def assertion_for(
    intervals: tuple[VersionInterval, ...] = (),
    *,
    explicit_versions: tuple[str, ...] = (),
    scheme: str = "pep440",
    ecosystem: str = "PyPI",
    package_key: str = "pkg:pypi/fixture-package",
) -> VersionAssertionValue:
    return VersionAssertionValue.model_validate(
        {
            "package_key": package_key,
            "ecosystem": ecosystem,
            "scheme": scheme,
            "raw_expression": "synthetic bounded algorithm input",
            "intervals": intervals,
            "explicit_versions": explicit_versions,
            "comparison_support": "supported",
        }
    )


def test_t26_c01_inside_introduced_fixed_range() -> None:
    assertion = assertion_for((VersionInterval(introduced="1.0.0", fixed="1.4.2"),))
    result = evaluate_version_assertion(
        assertion,
        package_key=assertion.package_key,
        ecosystem="PyPI",
        version="1.4.1",
        version_scheme="pep440",
    )
    assert result.status == "affected"
    assert result.reason == "matching_interval"
    assert result.interval_results[0].status == "affected"


def test_t26_c02_fixed_boundary_is_not_included() -> None:
    assertion = assertion_for((VersionInterval(introduced="1.0.0", fixed="1.4.2"),))
    result = evaluate_version_assertion(
        assertion,
        package_key=assertion.package_key,
        ecosystem="PyPI",
        version="1.4.2",
        version_scheme="pep440",
        range_complete=True,
    )
    assert result.status == "not_affected"
    assert result.reason == "outside_complete_range"


@pytest.mark.parametrize("scheme,ecosystem", [("pep440", "PyPI"), ("semver", "npm")])
def test_t26_c03_numeric_release_order(scheme: str, ecosystem: str) -> None:
    result = compare_versions("1.10.0", "1.9.0", scheme=scheme, ecosystem=ecosystem)
    assert result.status == "comparable"
    assert result.ordering == 1
    assert result.reason == "parsed_exact_versions"


@pytest.mark.parametrize(
    "version,branch,status",
    [
        ("1.4.0rc1", "1.x", "affected"),
        ("1.4.0", "1.x", "not_affected"),
        ("2.0.0", "2.x", "affected"),
        ("2.1.0", "2.x", "not_affected"),
        ("3.0.0", "3.x", "not_affected"),
        ("2.0.0", None, "unknown"),
    ],
)
def test_t26_c04_prerelease_independent_maintenance_branches(
    version: str, branch: str | None, status: str
) -> None:
    assertion = assertion_for(
        (
            VersionInterval(introduced="1.0.0", fixed="1.4.0", branch="1.x"),
            VersionInterval(introduced="2.0.0", last_affected="2.0.0", branch="2.x"),
        )
    )
    result = evaluate_version_assertion(
        assertion,
        package_key=assertion.package_key,
        ecosystem="PyPI",
        version=version,
        version_scheme="pep440",
        branch=branch,
        range_complete=True,
    )
    assert result.status == status
    assert len(result.interval_results) == 2


@pytest.mark.parametrize(
    "version,scheme,status,reason",
    [
        (None, "pep440", "unknown", "missing_version"),
        ("", "pep440", "unknown", "invalid_version"),
        ("1; print('execute')", "pep440", "unknown", "invalid_version"),
        ("a" * 40, "git", "unsupported", "unsupported_scheme"),
        ("1.0.0", "unknown", "unsupported", "unsupported_scheme"),
    ],
)
def test_t26_c05_missing_invalid_and_git_versions(
    version: str | None, scheme: str, status: str, reason: str
) -> None:
    assertion = assertion_for((VersionInterval(introduced="1.0.0"),), scheme=scheme)
    result = evaluate_version_assertion(
        assertion,
        package_key=assertion.package_key,
        ecosystem="PyPI",
        version=version,
        version_scheme=scheme,
        range_complete=True,
    )
    assert (result.status, result.reason) == (status, reason)


@pytest.mark.parametrize(
    "package_key,ecosystem,downstream_backport,reason",
    [
        ("pkg:npm/fixture-package", "npm", False, "ecosystem_mismatch"),
        ("pkg:pypi/other-package", "PyPI", False, "package_mismatch"),
        ("pkg:pypi/fixture-package?repository_url=private", "PyPI", False, "package_mismatch"),
        ("pkg:pypi/fixture-package", "PyPI", True, "downstream_backport_unverified"),
    ],
)
def test_t26_c06_identity_and_backport_are_not_guessed(
    package_key: str, ecosystem: str, downstream_backport: bool, reason: str
) -> None:
    assertion = assertion_for((VersionInterval(introduced="1.0.0", fixed="2.0.0"),))
    result = evaluate_version_assertion(
        assertion,
        package_key=package_key,
        ecosystem=ecosystem,
        version="2.0.0",
        version_scheme="pep440",
        downstream_backport=downstream_backport,
        range_complete=True,
    )
    assert result.status == "unknown"
    assert result.reason == reason


@pytest.mark.parametrize(
    "scheme,ecosystem,left,right,ordering",
    [
        ("pep440", "PyPI", "1.0", "1.0.0", 0),
        ("pep440", "PyPI", "1.0.dev1", "1.0a1", -1),
        ("pep440", "PyPI", "1.0rc1", "1.0", -1),
        ("pep440", "PyPI", "1.0.post1", "1.0", 1),
        ("pep440", "PyPI", "1!1.0", "9.0", 1),
        ("pep440", "PyPI", "1.0+vendor.1", "1.0", 1),
        ("semver", "npm", "1.0.0-alpha.2", "1.0.0-alpha.10", -1),
        ("semver", "npm", "1.0.0-rc.1", "1.0.0", -1),
        ("semver", "npm", "1.0.0+vendor.1", "1.0.0+vendor.2", 0),
        ("osv_ecosystem", "PyPI", "1.0rc1", "1.0", -1),
        ("osv_ecosystem", "npm", "1.0.0-rc.1", "1.0.0", -1),
    ],
)
def test_mature_comparators_preserve_distinct_ecosystem_semantics(
    scheme: str, ecosystem: str, left: str, right: str, ordering: int
) -> None:
    result = compare_versions(left, right, scheme=scheme, ecosystem=ecosystem)
    assert (result.status, result.ordering) == ("comparable", ordering)
    reverse = compare_versions(right, left, scheme=scheme, ecosystem=ecosystem)
    assert reverse.ordering == -ordering


@pytest.mark.parametrize("version", ["1", "1.2", "01.2.3", "v1.2.3", "1.2.3-01", "1.2.3rc1"])
def test_semver_does_not_coerce_incomplete_or_pep440_versions(version: str) -> None:
    result = compare_versions(version, "2.0.0", scheme="semver", ecosystem="npm")
    assert (result.status, result.ordering, result.reason) == ("unknown", None, "invalid_version")


@pytest.mark.parametrize(
    "scheme,ecosystem", [("pep440", "npm"), ("semver", "PyPI"), ("osv_ecosystem", "Debian")]
)
def test_wrong_scheme_and_unadapted_ecosystem_are_unsupported(scheme: str, ecosystem: str) -> None:
    result = compare_versions("1.0.0", "2.0.0", scheme=scheme, ecosystem=ecosystem)
    assert (result.status, result.ordering) == ("unsupported", None)


@pytest.mark.parametrize(
    "version,interval,status",
    [
        ("1.0.0", VersionInterval(introduced="1.0.0", fixed="2.0.0"), "affected"),
        ("0.9.0", VersionInterval(introduced="1.0.0", fixed="2.0.0"), "not_affected"),
        ("2.0.0", VersionInterval(introduced="1.0.0", fixed="2.0.0"), "not_affected"),
        ("2.0.0", VersionInterval(introduced="1.0.0", last_affected="2.0.0"), "affected"),
        ("2.0.1", VersionInterval(introduced="1.0.0", last_affected="2.0.0"), "not_affected"),
        ("0.0.0-alpha", VersionInterval(introduced="0", fixed="1.0.0"), "affected"),
        ("99.0.0", VersionInterval(introduced="2.0.0"), "affected"),
        ("0.1.0", VersionInterval(fixed="2.0.0"), "affected"),
        ("1.0.0", VersionInterval(introduced="2.0.0", fixed="1.0.0"), "unknown"),
        ("1.0.0", VersionInterval(introduced="1.0.0", fixed="1.0.0"), "unknown"),
        ("1.0.0", VersionInterval(introduced="1.0.0", fixed="invalid"), "unknown"),
    ],
)
def test_contains_version_boundaries(version: str, interval: VersionInterval, status: str) -> None:
    result = contains_version(version, interval, scheme="semver", ecosystem="npm")
    assert result.status == status


@pytest.mark.parametrize(
    "version,expected", [("1.2.0", "affected"), ("1.5.0", "not_affected"), ("2.1.0", "affected")]
)
def test_non_contiguous_intervals_are_not_flattened(version: str, expected: str) -> None:
    assertion = assertion_for(
        (
            VersionInterval(introduced="1.0", fixed="1.4"),
            VersionInterval(introduced="2.0", fixed="2.2"),
        )
    )
    result = evaluate_version_assertion(
        assertion,
        package_key=assertion.package_key,
        ecosystem="PyPI",
        version=version,
        version_scheme="pep440",
        range_complete=True,
    )
    assert result.status == expected
    assert len(result.interval_results) == 2


def test_incomplete_negative_range_defaults_to_unknown() -> None:
    assertion = assertion_for((VersionInterval(introduced="1.0", fixed="2.0"),))
    result = evaluate_version_assertion(
        assertion,
        package_key=assertion.package_key,
        ecosystem="PyPI",
        version="3.0",
        version_scheme="pep440",
    )
    assert (result.status, result.reason) == ("unknown", "range_completeness_unknown")


@pytest.mark.parametrize("version,expected", [("1.2", "affected"), ("3.0", "unknown")])
def test_partial_range_keeps_valid_match_and_invalid_segment(version: str, expected: str) -> None:
    assertion = assertion_for(
        (VersionInterval(introduced="1.0", fixed="2.0"), VersionInterval(fixed="invalid"))
    )
    result = evaluate_version_assertion(
        assertion,
        package_key=assertion.package_key,
        ecosystem="PyPI",
        version=version,
        version_scheme="pep440",
        range_complete=True,
    )
    assert result.status == expected
    assert result.interval_results[1].status == "unknown"
    assert result.interval_results[1].reason == "invalid_boundary"


def test_explicit_versions_are_independent_of_intervals() -> None:
    assertion = assertion_for(
        (VersionInterval(introduced="1.0", fixed="2.0"),), explicit_versions=("3.0",)
    )
    result = evaluate_version_assertion(
        assertion,
        package_key=assertion.package_key,
        ecosystem="PyPI",
        version="3.0.0",
        version_scheme="pep440",
    )
    assert (result.status, result.reason) == ("affected", "matching_explicit_version")


def test_invalid_explicit_version_cannot_make_negative_complete() -> None:
    assertion = assertion_for(explicit_versions=("1.0", "invalid"))
    result = evaluate_version_assertion(
        assertion,
        package_key=assertion.package_key,
        ecosystem="PyPI",
        version="3.0",
        version_scheme="pep440",
        range_complete=True,
    )
    assert (result.status, result.reason) == ("unknown", "invalid_explicit_version")


@pytest.mark.parametrize(
    "excluded,version,expected,reason",
    [
        ("1.2", "1.2.0", "not_affected", "explicitly_excluded"),
        ("invalid", "1.2", "unknown", "invalid_excluded_version"),
        ("1.3", "1.2", "affected", "matching_interval"),
    ],
)
def test_exclusions_have_explicit_normalized_semantics(
    excluded: str, version: str, expected: str, reason: str
) -> None:
    assertion = assertion_for((VersionInterval(introduced="1.0", fixed="2.0"),))
    result = evaluate_version_assertion(
        assertion,
        package_key=assertion.package_key,
        ecosystem="PyPI",
        version=version,
        version_scheme="pep440",
        excluded_versions=(excluded,),
    )
    assert (result.status, result.reason) == (expected, reason)


def test_mitigation_text_and_raw_expression_do_not_prove_range_or_fix() -> None:
    assertion = assertion_for().model_copy(
        update={
            "mitigations": ("disable vulnerable feature",),
            "vendor_fix": "upgrade",
            "raw_expression": "<2.0 || >=3.0",
        }
    )
    result = evaluate_version_assertion(
        assertion,
        package_key=assertion.package_key,
        ecosystem="PyPI",
        version="3.0",
        version_scheme="pep440",
        range_complete=True,
    )
    assert (result.status, result.reason) == ("unknown", "missing_range")


def test_osv_adapter_matches_explicit_asset_scheme() -> None:
    assertion = assertion_for(
        (VersionInterval(introduced="0", fixed="1.0"),), scheme="osv_ecosystem"
    )
    result = evaluate_version_assertion(
        assertion,
        package_key=assertion.package_key,
        ecosystem="PyPI",
        version="0.9",
        version_scheme="pep440",
    )
    assert result.status == "affected"


@pytest.mark.parametrize(
    "support,expected", [("unknown", "unknown"), ("unsupported", "unsupported")]
)
def test_source_comparison_support_is_not_overridden(support: str, expected: str) -> None:
    assertion = assertion_for((VersionInterval(introduced="1.0"),)).model_copy(
        update={"comparison_support": support}
    )
    result = evaluate_version_assertion(
        assertion,
        package_key=assertion.package_key,
        ecosystem="PyPI",
        version="2.0",
        version_scheme="pep440",
        range_complete=True,
    )
    assert result.status == expected
    assert result.reason == "source_comparison_" + support


def test_asset_version_scheme_cannot_be_guessed() -> None:
    assertion = assertion_for((VersionInterval(introduced="1.0"),))
    result = evaluate_version_assertion(
        assertion,
        package_key=assertion.package_key,
        ecosystem="PyPI",
        version="2.0",
        version_scheme="semver",
        range_complete=True,
    )
    assert (result.status, result.reason) == ("unsupported", "scheme_ecosystem_mismatch")


@pytest.mark.parametrize("version", ["1" * 129, "1.0\n", " 1.0 ", "1.0\x00"])
def test_exact_version_input_limit_and_control_characters(version: str) -> None:
    result = compare_versions(version, "2.0", scheme="pep440", ecosystem="PyPI")
    assert (result.status, result.ordering) == ("unknown", None)


def test_bounded_intervals_and_exclusions_reject_bypassed_contract() -> None:
    assertion = assertion_for((VersionInterval(introduced="1.0"),)).model_copy(
        update={"intervals": (VersionInterval(introduced="1.0"),) * 51}
    )
    result = evaluate_version_assertion(
        assertion,
        package_key=assertion.package_key,
        ecosystem="PyPI",
        version="2.0",
        version_scheme="pep440",
    )
    assert (result.status, result.reason) == ("unknown", "input_limit_exceeded")
    normal = assertion_for((VersionInterval(introduced="1.0"),))
    result = evaluate_version_assertion(
        normal,
        package_key=normal.package_key,
        ecosystem="PyPI",
        version="2.0",
        version_scheme="pep440",
        excluded_versions=("1.0",) * 51,
    )
    assert (result.status, result.reason) == ("unknown", "input_limit_exceeded")


def test_pure_comparison_is_deterministic_under_concurrent_calls() -> None:
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [
            executor.submit(compare_versions, "1.10.0", "1.9.0", scheme="semver", ecosystem="npm")
            for _ in range(32)
        ]
        results = [future.result() for future in futures]
    assert all(result.status == "comparable" and result.ordering == 1 for result in results)


@pytest.mark.parametrize("version", ["1.0", "1" * 128])
def test_precise_version_at_bounded_limit_is_comparable(version: str) -> None:
    result = compare_versions(version, version, scheme="pep440", ecosystem="PyPI")
    assert (result.status, result.ordering) == ("comparable", 0)


def test_single_version_closed_interval_includes_both_equal_boundaries() -> None:
    result = contains_version(
        "1.2.3",
        VersionInterval(introduced="1.2.3", last_affected="1.2.3"),
        scheme="semver",
        ecosystem="npm",
    )
    assert result.status == "affected"


@pytest.mark.parametrize("version", ["1.2", "3.0"])
def test_known_positive_keeps_unparseable_explicit_version_gap(version: str) -> None:
    assertion = assertion_for(
        (VersionInterval(introduced="1.0", fixed="2.0"),),
        explicit_versions=("3.0", "invalid"),
    )
    result = evaluate_version_assertion(
        assertion,
        package_key=assertion.package_key,
        ecosystem="PyPI",
        version=version,
        version_scheme="pep440",
    )
    assert result.status == "affected"
    assert "invalid_explicit_version" in result.unresolved_reasons


def test_no_positive_evaluation_can_hide_invalid_later_exclusion() -> None:
    assertion = assertion_for((VersionInterval(introduced="1.0", fixed="2.0"),))
    result = evaluate_version_assertion(
        assertion,
        package_key=assertion.package_key,
        ecosystem="PyPI",
        version="1.2",
        version_scheme="pep440",
        excluded_versions=("1.2", "invalid"),
        range_complete=True,
    )
    assert (result.status, result.reason) == ("unknown", "invalid_excluded_version")


def test_explicit_and_excluded_versions_at_existing_limits_are_supported() -> None:
    assertion = assertion_for(explicit_versions=("1.0",) * 100)
    result = evaluate_version_assertion(
        assertion,
        package_key=assertion.package_key,
        ecosystem="PyPI",
        version="1.0",
        version_scheme="pep440",
        excluded_versions=("2.0",) * 50,
    )
    assert result.status == "affected"


@pytest.mark.parametrize("identity_field", ["package", "ecosystem"])
def test_missing_identity_does_not_prove_absence(identity_field: str) -> None:
    assertion = assertion_for((VersionInterval(introduced="1.0"),))
    result = evaluate_version_assertion(
        assertion,
        package_key="" if identity_field == "package" else assertion.package_key,
        ecosystem="" if identity_field == "ecosystem" else "PyPI",
        version="2.0",
        version_scheme="pep440",
        range_complete=True,
    )
    assert (result.status, result.reason) == ("unknown", "missing_package_identity")


@pytest.mark.parametrize(
    "scheme,ecosystem,ordered_versions",
    [
        ("pep440", "PyPI", ("1.0.dev1", "1.0a1", "1.0b1", "1.0rc1", "1.0", "1.0.post1")),
        (
            "semver",
            "npm",
            (
                "1.0.0-alpha",
                "1.0.0-alpha.1",
                "1.0.0-alpha.beta",
                "1.0.0-beta",
                "1.0.0-beta.2",
                "1.0.0-beta.11",
                "1.0.0-rc.1",
                "1.0.0",
            ),
        ),
    ],
)
def test_independent_specification_order_is_transitive(
    scheme: str, ecosystem: str, ordered_versions: tuple[str, ...]
) -> None:
    for index, lower in enumerate(ordered_versions):
        for higher in ordered_versions[index + 1 :]:
            result = compare_versions(lower, higher, scheme=scheme, ecosystem=ecosystem)
            assert (result.status, result.ordering) == ("comparable", -1)
