"""Bounded version rules use mature exact-version parsers and preserve incomplete evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from packaging.version import Version as Pep440Version
from semver import Version as SemverVersion

from ai_intel.domain.enrichment_values import VersionAssertionValue, VersionInterval

MAX_VERSION_LENGTH = 128
MAX_BRANCH_LENGTH = 200
MAX_INTERVALS = 50
MAX_EXCLUDED_VERSIONS = 50
MAX_EXPLICIT_VERSIONS = 100
ParsedVersion = Pep440Version | SemverVersion
VersionStatus = Literal["affected", "not_affected", "unknown", "unsupported"]


@dataclass(frozen=True)
class VersionComparison:
    """Absent ordering is an explicit parse/support gap, never equal or less than."""

    status: Literal["comparable", "unknown", "unsupported"]
    ordering: int | None
    reason: str


@dataclass(frozen=True)
class VersionMatch:
    """Interval results retain source order, including undecidable branches of a known hit."""

    status: VersionStatus
    reason: str
    interval_results: tuple[VersionMatch, ...] = ()
    unresolved_reasons: tuple[str, ...] = ()


def _comparison_scheme(scheme: str, ecosystem: str) -> tuple[str | None, str]:
    if scheme not in {"pep440", "semver", "osv_ecosystem"}:
        return None, "unsupported_scheme"
    ecosystem_scheme = {"PyPI": "pep440", "npm": "semver"}.get(ecosystem)
    if ecosystem_scheme is None:
        return None, "unsupported_ecosystem"
    if scheme != "osv_ecosystem" and scheme != ecosystem_scheme:
        return None, "scheme_ecosystem_mismatch"
    return ecosystem_scheme, ""


def _valid_branch_label(branch: object) -> bool:
    """None preserves missing context; labels retain exact identity within frozen Label bounds."""
    return branch is None or (
        type(branch) is str
        and 0 < len(branch) <= MAX_BRANCH_LENGTH
        and branch == branch.strip()
        and branch.isprintable()
    )


def _parse_exact_version(version: str, scheme: str) -> ParsedVersion:
    if (
        not version
        or len(version) > MAX_VERSION_LENGTH
        or version != version.strip()
        or any(ord(character) < 32 or ord(character) == 127 for character in version)
    ):
        raise ValueError("exact version must be bounded and have no surrounding whitespace/control")
    if scheme == "pep440":
        return Pep440Version(version)
    return SemverVersion.parse(version)


def _compare_parsed_versions(left: ParsedVersion, right: ParsedVersion) -> int:
    if isinstance(left, Pep440Version) and isinstance(right, Pep440Version):
        return int(left > right) - int(left < right)
    if isinstance(left, SemverVersion) and isinstance(right, SemverVersion):
        return left.compare(right)
    raise ValueError("versions from distinct schemes cannot be compared")


def compare_versions(
    left_version: str | None, right_version: str | None, *, scheme: str, ecosystem: str
) -> VersionComparison:
    """Compare precise versions only; OSV ECOSYSTEM is explicitly adapted for PyPI and npm."""
    resolved_scheme, reason = _comparison_scheme(scheme, ecosystem)
    if resolved_scheme is None:
        return VersionComparison("unsupported", None, reason)
    if left_version is None or right_version is None:
        return VersionComparison("unknown", None, "missing_version")
    try:
        left = _parse_exact_version(left_version, resolved_scheme)
        right = _parse_exact_version(right_version, resolved_scheme)
    except ValueError:
        return VersionComparison("unknown", None, "invalid_version")
    return VersionComparison(
        "comparable", _compare_parsed_versions(left, right), "parsed_exact_versions"
    )


def contains_version(
    version: str | None,
    interval: VersionInterval,
    *,
    scheme: str,
    ecosystem: str,
    branch: str | None = None,
) -> VersionMatch:
    """Check one normalized interval; introduced '0' is the OSV all-versions sentinel."""
    resolved_scheme, reason = _comparison_scheme(scheme, ecosystem)
    if resolved_scheme is None:
        return VersionMatch("unsupported", reason)
    if version is None:
        return VersionMatch("unknown", "missing_version")
    try:
        parsed_version = _parse_exact_version(version, resolved_scheme)
    except ValueError:
        return VersionMatch("unknown", "invalid_version")
    return _contains_parsed_version(parsed_version, interval, resolved_scheme, branch)


def _contains_parsed_version(
    version: ParsedVersion, interval: VersionInterval, scheme: str, branch: str | None
) -> VersionMatch:
    if not _valid_branch_label(branch):
        return VersionMatch("unknown", "invalid_asset_branch")
    if not _valid_branch_label(interval.branch):
        return VersionMatch("unknown", "invalid_source_branch")
    if interval.branch is not None:
        if branch is None:
            return VersionMatch("unknown", "missing_branch")
        if interval.branch != branch:
            return VersionMatch("not_affected", "branch_mismatch")
    if interval.fixed is not None and interval.last_affected is not None:
        return VersionMatch("unknown", "ambiguous_upper_boundary")
    if interval.introduced is None and interval.fixed is None and interval.last_affected is None:
        return VersionMatch("unknown", "missing_boundary")
    try:
        introduced = None
        if interval.introduced is not None and interval.introduced != "0":
            introduced = _parse_exact_version(interval.introduced, scheme)
        upper_text = interval.fixed if interval.fixed is not None else interval.last_affected
        upper = _parse_exact_version(upper_text, scheme) if upper_text is not None else None
    except ValueError:
        return VersionMatch("unknown", "invalid_boundary")
    if introduced is not None and upper is not None:
        ordering = _compare_parsed_versions(introduced, upper)
        if ordering > 0 or (ordering == 0 and interval.fixed is not None):
            return VersionMatch("unknown", "invalid_interval_order")
    if introduced is not None and _compare_parsed_versions(version, introduced) < 0:
        return VersionMatch("not_affected", "before_introduced")
    if upper is not None:
        ordering = _compare_parsed_versions(version, upper)
        if ordering > 0 or (ordering == 0 and interval.fixed is not None):
            return VersionMatch(
                "not_affected", "at_or_after_fixed" if interval.fixed else "after_last_affected"
            )
    return VersionMatch("affected", "inside_interval")


def evaluate_version_assertion(
    assertion: VersionAssertionValue,
    *,
    package_key: str,
    ecosystem: str,
    version: str | None,
    version_scheme: str,
    branch: str | None = None,
    downstream_backport: bool = False,
    excluded_versions: tuple[str, ...] = (),
    range_complete: bool = False,
) -> VersionMatch:
    """Evaluate a source assertion without inferring identity, completeness, or downstream fixes.

    Package keys, including purls, must match exactly. Only a caller with trusted completeness
    evidence may set range_complete. Exclusions are exact versions already backed by that caller's
    evidence. A downstream backport requires a separate authoritative assessment and stays unknown
    here. This result is a version condition, not a complete asset or mitigation assessment.
    """
    if type(range_complete) is not bool or type(downstream_backport) is not bool:
        return VersionMatch("unknown", "invalid_evaluation_context")
    if not package_key or not ecosystem:
        return VersionMatch("unknown", "missing_package_identity")
    if ecosystem != assertion.ecosystem:
        return VersionMatch("unknown", "ecosystem_mismatch")
    if package_key != assertion.package_key:
        return VersionMatch("unknown", "package_mismatch")
    if assertion.comparison_support == "unsupported":
        return VersionMatch("unsupported", "source_comparison_unsupported")
    if assertion.comparison_support != "supported":
        return VersionMatch("unknown", "source_comparison_unknown")
    resolved_scheme, reason = _comparison_scheme(assertion.scheme, ecosystem)
    if resolved_scheme is None:
        return VersionMatch("unsupported", reason)
    asset_scheme, reason = _comparison_scheme(version_scheme, ecosystem)
    if asset_scheme is None:
        return VersionMatch("unsupported", reason)
    if resolved_scheme != asset_scheme:
        return VersionMatch("unsupported", "version_scheme_mismatch")
    if (
        len(assertion.intervals) > MAX_INTERVALS
        or len(assertion.explicit_versions) > MAX_EXPLICIT_VERSIONS
        or len(excluded_versions) > MAX_EXCLUDED_VERSIONS
    ):
        return VersionMatch("unknown", "input_limit_exceeded")
    if downstream_backport:
        return VersionMatch("unknown", "downstream_backport_unverified")
    if version is None:
        return VersionMatch("unknown", "missing_version")
    try:
        parsed_version = _parse_exact_version(version, resolved_scheme)
    except ValueError:
        return VersionMatch("unknown", "invalid_version")
    if not assertion.intervals and not assertion.explicit_versions:
        return VersionMatch("unknown", "missing_range")
    interval_results = tuple(
        _contains_parsed_version(parsed_version, interval, resolved_scheme, branch)
        for interval in assertion.intervals
    )
    excluded_match = False
    try:
        for excluded in excluded_versions:
            parsed_excluded = _parse_exact_version(excluded, resolved_scheme)
            excluded_match |= _compare_parsed_versions(parsed_version, parsed_excluded) == 0
    except ValueError:
        return VersionMatch("unknown", "invalid_excluded_version", interval_results)
    explicit_match = False
    invalid_explicit_version = False
    for explicit in assertion.explicit_versions:
        try:
            parsed_explicit = _parse_exact_version(explicit, resolved_scheme)
        except ValueError:
            invalid_explicit_version = True
            continue
        explicit_match |= _compare_parsed_versions(parsed_version, parsed_explicit) == 0
    unresolved_reasons = tuple(
        result.reason for result in interval_results if result.status in {"unknown", "unsupported"}
    )
    if invalid_explicit_version:
        unresolved_reasons += ("invalid_explicit_version",)
    if not _valid_branch_label(branch):
        if "invalid_asset_branch" not in unresolved_reasons:
            unresolved_reasons += ("invalid_asset_branch",)
        return VersionMatch("unknown", "invalid_asset_branch", interval_results, unresolved_reasons)
    if excluded_match:
        return VersionMatch(
            "not_affected", "explicitly_excluded", interval_results, unresolved_reasons
        )
    if explicit_match:
        return VersionMatch(
            "affected", "matching_explicit_version", interval_results, unresolved_reasons
        )
    if any(result.status == "affected" for result in interval_results):
        return VersionMatch("affected", "matching_interval", interval_results, unresolved_reasons)
    if invalid_explicit_version:
        return VersionMatch(
            "unknown", "invalid_explicit_version", interval_results, unresolved_reasons
        )
    if any(result.status in {"unknown", "unsupported"} for result in interval_results):
        return VersionMatch(
            "unknown", "incomplete_interval_evaluation", interval_results, unresolved_reasons
        )
    if not range_complete:
        return VersionMatch("unknown", "range_completeness_unknown", interval_results)
    return VersionMatch("not_affected", "outside_complete_range", interval_results)
