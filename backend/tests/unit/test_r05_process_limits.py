"""Native limits are applied only inside disposable children, including negative CPU tests."""

import os
import subprocess
import sys

import pytest

from ai_intel.infrastructure.process_limits import bound_process_resources


@pytest.mark.parametrize("memory_bytes", [True, False, 0, -1, 2 * 1024**3 + 1, 1.5])
def test_memory_limit_requires_bounded_integer(memory_bytes: int) -> None:
    with pytest.raises(ValueError, match="memory_bytes"):
        bound_process_resources(memory_bytes=memory_bytes, cpu_seconds=1)


@pytest.mark.parametrize("cpu_seconds", [True, False, 0, -1, 31, 1.5])
def test_cpu_limit_requires_bounded_integer(cpu_seconds: int) -> None:
    with pytest.raises(ValueError, match="cpu_seconds"):
        bound_process_resources(memory_bytes=100 * 1024**2, cpu_seconds=cpu_seconds)


def test_real_native_memory_limit_refuses_large_allocation() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from ai_intel.infrastructure.process_limits import bound_process_resources; "
            "handle = bound_process_resources(memory_bytes=100*1024**2,cpu_seconds=5); "
            "print('LIMIT_APPLIED',flush=True); allocation=bytearray(200*1024**2); "
            "print('UNEXPECTED_ALLOCATION',flush=True)",
        ],
        capture_output=True,
        timeout=8,
        check=False,
    )
    assert b"LIMIT_APPLIED" in result.stdout
    assert b"UNEXPECTED_ALLOCATION" not in result.stdout
    assert result.returncode != 0
    assert b"MemoryError" in result.stderr or result.returncode < 0


def test_real_native_cpu_limit_terminates_busy_child() -> None:
    code = (
        "from ai_intel.infrastructure.process_limits import bound_process_resources\n"
        "handle = bound_process_resources(memory_bytes=100*1024**2,cpu_seconds=1)\n"
        "print('LIMIT_APPLIED',flush=True)\n"
        "while True:\n    pass\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, timeout=8, check=False
    )
    assert b"LIMIT_APPLIED" in result.stdout
    assert result.returncode != 0
    assert b"Traceback" not in result.stderr


def test_unsupported_platform_refuses_unbounded_execution(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "unsupported")
    monkeypatch.setattr(os, "name", "posix")
    with pytest.raises(OSError, match="unavailable"):
        bound_process_resources(memory_bytes=100 * 1024**2, cpu_seconds=1)


def test_pdf_retains_memory_and_cpu_envelope(monkeypatch: pytest.MonkeyPatch) -> None:
    from ai_intel.ingestion.parsing import _pdf_worker

    observed: list[tuple[int, int]] = []

    def bound(*, memory_bytes: int, cpu_seconds: int) -> int:
        observed.append((memory_bytes, cpu_seconds))
        return 42

    monkeypatch.setattr(_pdf_worker, "bound_process_resources", bound)
    assert _pdf_worker._bound_memory() == 42
    assert observed == [(512 * 1024**2, 15)]
