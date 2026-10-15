"""Version text is inert input even when it looks like Python, shell, URL, or SQL."""

from __future__ import annotations

import builtins
import os
import socket
import subprocess

import pytest

from ai_intel.assessment.version_ranges import evaluate_version_assertion
from ai_intel.domain.enrichment_values import VersionAssertionValue, VersionInterval


@pytest.mark.parametrize(
    "version",
    [
        "__import__('os').system('exit 99')",
        "$(whoami)",
        "1.0; Get-Content Env:*",
        "https://127.0.0.1/private",
        "1.0' OR 1=1; DROP TABLE claims; --",
        "1.0\x00",
        "1" * 129,
    ],
)
def test_version_evaluation_never_executes_text_or_performs_io(
    version: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    assertion = VersionAssertionValue(
        package_key="pkg:pypi/fixture-package",
        ecosystem="PyPI",
        scheme="pep440",
        raw_expression="synthetic inert source input",
        intervals=(VersionInterval(introduced="1.0", fixed="2.0"),),
        comparison_support="supported",
    )

    def forbidden_call(*args: object, **kwargs: object) -> None:
        pytest.fail("pure version evaluation attempted execution or IO")

    with monkeypatch.context() as context:
        context.setattr(builtins, "eval", forbidden_call)
        context.setattr(builtins, "exec", forbidden_call)
        context.setattr(os, "system", forbidden_call)
        context.setattr(subprocess, "run", forbidden_call)
        context.setattr(subprocess, "Popen", forbidden_call)
        context.setattr(socket, "create_connection", forbidden_call)
        result = evaluate_version_assertion(
            assertion,
            package_key=assertion.package_key,
            ecosystem=assertion.ecosystem,
            version=version,
            version_scheme="pep440",
            range_complete=True,
        )
    assert (result.status, result.reason) == ("unknown", "invalid_version")


def test_valid_version_evaluation_has_no_io(monkeypatch: pytest.MonkeyPatch) -> None:
    assertion = VersionAssertionValue(
        package_key="pkg:npm/fixture-package",
        ecosystem="npm",
        scheme="semver",
        raw_expression="synthetic exact semver interval",
        intervals=(VersionInterval(introduced="1.0.0", fixed="2.0.0"),),
        comparison_support="supported",
    )

    def forbidden_call(*args: object, **kwargs: object) -> None:
        pytest.fail("pure version evaluation attempted execution or IO")

    with monkeypatch.context() as context:
        context.setattr(builtins, "eval", forbidden_call)
        context.setattr(builtins, "exec", forbidden_call)
        context.setattr(subprocess, "run", forbidden_call)
        context.setattr(socket, "create_connection", forbidden_call)
        result = evaluate_version_assertion(
            assertion,
            package_key=assertion.package_key,
            ecosystem=assertion.ecosystem,
            version="1.2.3-rc.1",
            version_scheme="semver",
        )
    assert result.status == "affected"
