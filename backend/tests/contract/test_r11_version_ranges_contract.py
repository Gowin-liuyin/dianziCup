"""The algorithm consumes the frozen R07 value contract without rewriting its source facts."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest
from pydantic import ValidationError

from ai_intel.assessment.version_ranges import evaluate_version_assertion
from ai_intel.domain.enrichment_values import VersionAssertionValue, VersionInterval


def test_frozen_assertion_is_not_mutated_by_evaluation() -> None:
    assertion = VersionAssertionValue(
        package_key="pkg:pypi/fixture-package",
        ecosystem="PyPI",
        scheme="pep440",
        raw_expression="fixture source interval and mitigation",
        intervals=(VersionInterval(introduced="1.0", fixed="2.0"),),
        comparison_support="supported",
        vendor_fix="authority says upgrade to 2.0",
        mitigations=("disable vulnerable feature",),
        limitations=("branch coverage is partial",),
    )
    original = assertion.model_dump_json()
    result = evaluate_version_assertion(
        assertion,
        package_key=assertion.package_key,
        ecosystem=assertion.ecosystem,
        version="2.0",
        version_scheme=assertion.scheme,
    )
    assert result.status == "unknown"
    assert assertion.model_dump_json() == original
    with pytest.raises(FrozenInstanceError):
        result.reason = "safe"


def test_existing_interval_contract_keeps_fifty_interval_limit() -> None:
    assertion = VersionAssertionValue(
        package_key="pkg:pypi/fixture-package",
        ecosystem="PyPI",
        scheme="pep440",
        raw_expression="synthetic bounded interval limit",
        intervals=(VersionInterval(introduced="1.0", fixed="2.0"),) * 50,
        comparison_support="supported",
    )
    result = evaluate_version_assertion(
        assertion,
        package_key=assertion.package_key,
        ecosystem=assertion.ecosystem,
        version="1.1",
        version_scheme="pep440",
    )
    assert result.status == "affected"
    assert len(result.interval_results) == 50
    with pytest.raises(ValidationError, match="at most 50"):
        VersionAssertionValue.model_validate(
            assertion.model_dump() | {"intervals": assertion.intervals + assertion.intervals[:1]}
        )


def test_unknown_source_support_and_limitations_are_preserved() -> None:
    assertion = VersionAssertionValue(
        package_key="pkg:pypi/fixture-package",
        ecosystem="PyPI",
        scheme="pep440",
        raw_expression="source only: do not infer from an expression",
        intervals=(VersionInterval(introduced="1.0"),),
        limitations=("no verified comparison support",),
    )
    result = evaluate_version_assertion(
        assertion,
        package_key=assertion.package_key,
        ecosystem=assertion.ecosystem,
        version="2.0",
        version_scheme="pep440",
        range_complete=True,
    )
    assert (result.status, result.reason) == ("unknown", "source_comparison_unknown")
    assert assertion.limitations == ("no verified comparison support",)
