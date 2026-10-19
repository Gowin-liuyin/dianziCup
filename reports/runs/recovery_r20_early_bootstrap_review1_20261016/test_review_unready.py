"""One real fixed PDF worker must remain closed when the guardian never readies."""

from __future__ import annotations

import ctypes
import json
import subprocess
from ctypes import wintypes

import pytest

from ai_intel.infrastructure import process_limits


def test_unready_guard_reaps_fixed_worker_and_closes_setup_handles(monkeypatch: pytest.MonkeyPatch) -> None:
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.GetProcessHandleCount.argtypes = [wintypes.HANDLE, ctypes.c_void_p]

    def count_handles() -> int:
        count = wintypes.DWORD()
        assert kernel.GetProcessHandleCount(kernel.GetCurrentProcess(), ctypes.byref(count))
        return count.value

    processes = []
    original = subprocess.Popen

    def record_launch(*arguments, **keywords):
        process = original(*arguments, **keywords)
        processes.append(process)
        return process

    monkeypatch.setattr(process_limits.subprocess, "Popen", record_launch)
    monkeypatch.setattr(process_limits, "_WINDOWS_CPU_GUARD_CODE", "import time;time.sleep(20)")
    before = count_handles()
    with pytest.raises(OSError):
        process_limits._launch_windows_worker("pdf", memory_bytes=512 * 1024**2, cpu_seconds=15, environment={})
    assert len(processes) == 2
    assert all(process.poll() is not None for process in processes)
    worker = processes[0]
    output, error = worker.communicate(timeout=1)
    assert output == b"" and error is None
    for process in processes:
        for stream in (process.stdin, process.stdout, process.stderr):
            if stream is not None:
                stream.close()
        process._handle.Close()
    after = count_handles()
    print("UNREADY_OBSERVATION " + json.dumps({"pids": [process.pid for process in processes],
        "exit_codes": [process.returncode for process in processes], "handles_before": before,
        "handles_after_explicit_popen_owner_close": after, "output": output.decode()}))
    assert after == before
