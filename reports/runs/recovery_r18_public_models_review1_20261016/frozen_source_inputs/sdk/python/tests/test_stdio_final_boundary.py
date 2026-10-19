"""Explicit finalizer faults test fixed errors, classification and a real process exit."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from unittest.mock import patch

import pytest
from ai_intel_client import mcp_stdio
from ai_intel_client.client import ClientConfigurationError
from ai_intel_client.output_budget import OutputBudgetConfigurationError
from r18_test_paths import ROOT

MARKER = "synthetic-stdio-final-boundary-marker-no-product-secret"


@pytest.mark.parametrize(
    "exception,expected_code",
    [
        (RuntimeError, "backend_internal_error"),
        (ClientConfigurationError, "not_configured"),
        (OutputBudgetConfigurationError, "not_configured"),
    ],
)
def test_final_boundary_returns_failure_and_preserves_configuration_classification(
    exception: type[Exception],
    expected_code: str,
    capsys,
) -> None:
    error = exception(MARKER)

    def controlled_runner(coroutine):
        coroutine.close()
        raise error

    with patch.object(mcp_stdio.asyncio, "run", new=controlled_runner):
        assert mcp_stdio.main() == 3
    captured = capsys.readouterr()
    assert captured.out == ""
    assert json.loads(captured.err) == {"error": {"code": expected_code}}
    assert MARKER not in captured.err
    assert "Traceback" not in captured.err


def test_actual_process_finalizer_error_exits_three_with_safe_ascii_json() -> None:
    program = """from ai_intel_client import mcp_stdio
async def explicit_finalizer_fault():
    raise RuntimeError('synthetic-stdio-final-boundary-marker-no-product-secret')
mcp_stdio.serve_stdio = explicit_finalizer_fault
raise SystemExit(mcp_stdio.main())
"""
    result = subprocess.run(
        [sys.executable, "-c", program],
        cwd=ROOT,
        capture_output=True,
        timeout=10,
        check=False,
        env={
            "PYTHONPATH": str(ROOT / "sdk/python"),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONIOENCODING": "ascii",
            "SYSTEMROOT": os.environ.get("SYSTEMROOT", "C:/Windows"),
        },
    )
    assert result.returncode == 3
    assert result.stdout == b""
    assert json.loads(result.stderr) == {"error": {"code": "backend_internal_error"}}
    assert MARKER.encode() not in result.stderr
    assert b"Traceback" not in result.stderr
