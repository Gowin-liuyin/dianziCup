"""Startup ordering and exhausted initial CPU are distinct from sampled termination."""

from __future__ import annotations

import builtins
import ctypes
import json
import logging
import runpy
import sys
from io import BytesIO
from types import SimpleNamespace

import pytest

from ai_intel.infrastructure import process_limits


@pytest.mark.parametrize("limit_available", [True, False])
def test_pdf_imports_dependency_only_after_resource_limit(
    monkeypatch: pytest.MonkeyPatch, limit_available: bool
) -> None:
    """Observe actual imports; a denied limit must never reach pypdf initialization."""
    limit_applied = False
    imports: list[str] = []
    original_import = builtins.__import__
    original_logging_level = logging.root.manager.disable

    def apply_limit(*, memory_bytes: int, cpu_seconds: int) -> int:
        nonlocal limit_applied
        assert (memory_bytes, cpu_seconds) == (512 * 1024**2, 15)
        if not limit_available:
            raise OSError("synthetic resource refusal")
        limit_applied = True
        return 42

    def observe_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "pypdf" or name.startswith("pypdf."):
            assert limit_applied, "pypdf initialized before resource limit"
            imports.append(name)
        return original_import(name, *args, **kwargs)

    output = BytesIO()
    monkeypatch.setattr(process_limits, "bound_process_resources", apply_limit)
    monkeypatch.setattr(builtins, "__import__", observe_import)
    monkeypatch.setattr(sys, "stdin", SimpleNamespace(buffer=BytesIO(b"%PDF-1.4\n%%EOF")))
    monkeypatch.setattr(sys, "stdout", SimpleNamespace(buffer=output))
    try:
        runpy.run_module("ai_intel.ingestion.parsing._pdf_worker", run_name="__main__")
    finally:
        logging.disable(original_logging_level)
    response = json.loads(output.getvalue())
    assert response["pages"] == []
    if limit_available:
        assert imports
        assert response["notes"] == ["invalid or resource-limited pdf"]
    else:
        assert imports == []
        assert response["notes"] == ["pdf resource limit unavailable"]


@pytest.mark.parametrize("initial_cpu_ticks", [10_000_000, 10_156_250])
def test_guard_refuses_readiness_when_initial_total_cpu_is_exhausted(
    monkeypatch: pytest.MonkeyPatch, initial_cpu_ticks: int
) -> None:
    """GetProcessTimes' cumulative kernel plus user must be checked before SetEvent."""
    events: list[str] = []

    def successful_call(*arguments: object) -> int:
        return 1

    def get_process_times(handle: object, *arguments: object) -> int:
        arguments[2]._obj.value = initial_cpu_ticks // 2
        arguments[3]._obj.value = initial_cpu_ticks - initial_cpu_ticks // 2
        return 1

    def set_event(handle: object) -> int:
        events.append("ready")
        return 1

    def terminate_process(handle: object, exit_code: object) -> int:
        events.append("terminated")
        return 1

    kernel = SimpleNamespace(
        WaitForSingleObject=lambda *arguments: 0,
        GetProcessTimes=get_process_times,
        TerminateProcess=terminate_process,
        SetEvent=set_event,
        CloseHandle=successful_call,
        GetHandleInformation=successful_call,
    )
    monkeypatch.setattr(ctypes, "WinDLL", lambda *args, **kwargs: kernel, raising=False)
    monkeypatch.setattr(sys, "argv", ["guard", "1", "2", "3", "10000000"])
    with pytest.raises(OSError, match="exhausted"):
        exec(process_limits._WINDOWS_CPU_GUARD_CODE, {})
    assert events == ["terminated"]


def test_pdf_parent_filters_coverage_and_unrelated_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The production launch retains its fixed module and allowlisted environment."""
    from ai_intel.ingestion.parsing import pdf_text

    observed: dict[str, object] = {}

    def launch(command: list[str], **keywords: object) -> SimpleNamespace:
        observed.update(command=command, **keywords)
        return SimpleNamespace(
            returncode=0, communicate=lambda *args, **kwargs: (b'{"pages":[],"notes":[]}', None)
        )

    monkeypatch.setenv("COV_CORE_DATAFILE", "synthetic-coverage-marker")
    monkeypatch.setenv("SYNTHETIC_SECRET", "synthetic-isolated-marker")
    monkeypatch.setattr(pdf_text.subprocess, "Popen", launch)
    result = pdf_text.parse_pdf_text_layer(b"%PDF-1.4\n")
    assert result.status == "unparseable"
    assert observed["command"] == [sys.executable, "-m", "ai_intel.ingestion.parsing._pdf_worker"]
    assert set(observed["env"]) <= {
        "SYSTEMROOT",
        "WINDIR",
        "PATH",
        "PYTHONPATH",
        "TEMP",
        "TMP",
        "PYTHONUTF8",
        "PYTHONIOENCODING",
    }
