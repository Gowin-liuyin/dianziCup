"""Independent synthetic cases derived from T26 and the frozen source-value contract."""

import pytest

from ai_intel.assessment.version_ranges import compare_versions, contains_version, evaluate_version_assertion
from ai_intel.domain.enrichment_values import VersionAssertionValue, VersionInterval


def assertion(intervals=(), explicit=(), scheme="pep440", ecosystem="PyPI"):
    return VersionAssertionValue(package_key="pkg:pypi/review-fixture" if ecosystem == "PyPI" else "pkg:npm/review-fixture", ecosystem=ecosystem, scheme=scheme, raw_expression="independent synthetic review", intervals=intervals, explicit_versions=explicit, comparison_support="supported")


def evaluate(source, version, **context):
    return evaluate_version_assertion(source, package_key=source.package_key, ecosystem=source.ecosystem, version=version, version_scheme=source.scheme, **context)


@pytest.mark.parametrize("version,expected", [("1.4.1", "affected"), ("1.4.2", "not_affected"), ("0.9.9", "not_affected")], ids=["T26-C01", "T26-C02", "lower-bound"])
def test_independent_fixed_boundary(version, expected):
    source = assertion((VersionInterval(introduced="1.0.0", fixed="1.4.2"),))
    assert evaluate(source, version, range_complete=True).status == expected


@pytest.mark.parametrize("scheme,ecosystem", [("pep440", "PyPI"), ("semver", "npm")], ids=["T26-C03-pep440", "T26-C03-semver"])
def test_independent_release_order(scheme, ecosystem):
    assert compare_versions("1.10.0", "1.9.0", scheme=scheme, ecosystem=ecosystem).ordering == 1


@pytest.mark.parametrize("scheme,ecosystem,early,release", [("pep440", "PyPI", "1.0rc9", "1.0"), ("semver", "npm", "1.0.0-rc.9", "1.0.0")])
def test_independent_prerelease_order(scheme, ecosystem, early, release):
    assert compare_versions(early, release, scheme=scheme, ecosystem=ecosystem).ordering == -1


@pytest.mark.parametrize("version,branch,expected", [("1.2", "stable", "affected"), ("2.0", "preview", "affected"), ("1.5", "stable", "not_affected"), ("2.0", None, "unknown")], ids=["T26-C04-stable", "T26-C04-preview", "T26-C04-gap", "T26-C04-missing"])
def test_independent_multiple_branches(version, branch, expected):
    source = assertion((VersionInterval(introduced="1.0", fixed="1.4", branch="stable"), VersionInterval(introduced="2.0", last_affected="2.0", branch="preview")))
    result = evaluate(source, version, branch=branch, range_complete=True)
    assert result.status == expected
    assert len(result.interval_results) == 2


@pytest.mark.parametrize("version", [None, "garbage", "1.2\n", "1" * 129], ids=["T26-C05-missing", "T26-C05-invalid", "control", "length"])
def test_independent_invalid_version(version):
    assert evaluate(assertion((VersionInterval(introduced="0", fixed="2"),)), version, range_complete=True).status == "unknown"


@pytest.mark.parametrize("scheme,ecosystem", [("git", "PyPI"), ("osv_ecosystem", "Debian"), ("semver", "PyPI")])
def test_independent_unsupported_scheme(scheme, ecosystem):
    assert compare_versions("abcdef", "fedcba", scheme=scheme, ecosystem=ecosystem).status == "unsupported"


def test_independent_identity_and_backport():
    source = assertion((VersionInterval(introduced="0", fixed="2"),))
    assert evaluate_version_assertion(source, package_key="pkg:npm/review-fixture", ecosystem="npm", version="1.0", version_scheme="semver", range_complete=True).status == "unknown"
    assert evaluate_version_assertion(source, package_key="review-fixture", ecosystem="PyPI", version="1.0", version_scheme="pep440", range_complete=True).status == "unknown"
    assert evaluate(source, "2.0", downstream_backport=True, range_complete=True).status == "unknown"


@pytest.mark.parametrize("scheme,ecosystem,version,fixed", [("semver", "npm", "0.0.0-alpha", "0.0.0"), ("pep440", "PyPI", "0.dev0", "0")])
def test_osv_zero_is_universal_before_first_release(scheme, ecosystem, version, fixed):
    assert contains_version(version, VersionInterval(introduced="0", fixed=fixed), scheme=scheme, ecosystem=ecosystem).status == "affected"


def test_known_hit_preserves_unknown_branch():
    source = assertion((VersionInterval(introduced="0", fixed="2"), VersionInterval(introduced="0", fixed="4", branch="other")))
    result = evaluate(source, "1")
    assert result.status == "affected"
    assert result.interval_results[1].status == "unknown"
    assert result.unresolved_reasons == ("missing_branch",)


def test_incomplete_negative_cannot_be_safe():
    result = evaluate(assertion((VersionInterval(introduced="1", fixed="2"),)), "3")
    assert result.status == "unknown"


@pytest.mark.parametrize("version,expected", [("1.2.3", "affected"), ("1.2.4", "not_affected")])
def test_last_affected_is_closed(version, expected):
    source = assertion((VersionInterval(introduced="1.0.0", last_affected="1.2.3"),), scheme="semver", ecosystem="npm")
    assert evaluate(source, version, range_complete=True).status == expected


@pytest.mark.parametrize("excluded,expected", [(("1.2",), "not_affected"), (("1.3",), "affected"), (("1.2", "invalid"), "unknown")])
def test_independent_exclusions(excluded, expected):
    assert evaluate(assertion((VersionInterval(introduced="1", fixed="2"),)), "1.2", excluded_versions=excluded).status == expected


@pytest.mark.parametrize("branch", ["", " ", 1, True], ids=["empty", "whitespace", "integer", "boolean"])
def test_invalid_branch_context_cannot_prove_not_affected(branch):
    source = assertion((VersionInterval(introduced="1", fixed="2", branch="stable"),))
    result = evaluate(source, "1.5", branch=branch, range_complete=True)
    assert result.status == "unknown"


def test_exclusion_result_preserves_other_unresolved_source_evidence():
    source = assertion((VersionInterval(introduced="0", fixed="2", branch="stable"),), explicit=("invalid",))
    result = evaluate(source, "1.5", excluded_versions=("1.5",))
    assert result.status == "not_affected"
    assert result.interval_results[0].status == "unknown"
    assert "missing_branch" in result.unresolved_reasons
    assert "invalid_explicit_version" in result.unresolved_reasons
