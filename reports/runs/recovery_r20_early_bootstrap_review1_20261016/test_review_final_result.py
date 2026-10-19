"""Independent zero-worker checks of the final CPU query and result publication boundary."""

from __future__ import annotations

import ctypes
import threading

import pytest

from ai_intel.infrastructure import process_limits
from ai_intel.ingestion.parsing import pdf_text


def test_pdf_valid_output_is_rejected_when_close_discovers_supervision_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    class Process:
        returncode = 0

        def communicate(self, content: bytes, timeout: int) -> tuple[bytes, None]:
            assert content == b"%PDF-1.7\n" and timeout == 20
            return b'{"pages":[{"page_number":1,"text":"valid text"}],"notes":[]}', None

    class Supervisor:
        error = None

        def close(self) -> None:
            self.error = OSError("final cumulative CPU query failed")

    supervisor = Supervisor()
    monkeypatch.setattr(pdf_text, "_launch_windows_worker", lambda *args, **kwargs: (Process(), supervisor))
    result = pdf_text.parse_pdf_text_layer(b"%PDF-1.7\n")
    assert result.status == "unparseable"
    assert result.normalized_text == ""
    assert result.notes == ("pdf extraction process failed or exceeded resource limit",)


@pytest.mark.parametrize("ticks,api_failure", [(9_999_999, False), (10_000_000, False), (10_312_500, False), (0, True)])
def test_exited_worker_is_still_measured_and_query_failure_is_fail_closed(ticks: int, api_failure: bool) -> None:
    class Kernel:
        terminated = False
        closed = False

        def WaitForSingleObject(self, handle: int, timeout: int) -> int:
            return 0

        def GetProcessTimes(self, handle: int, *outputs: object) -> int:
            if api_failure:
                ctypes.set_last_error(6)
                return 0
            outputs[2]._obj.value = ticks
            outputs[3]._obj.value = 0
            return 1

        def TerminateProcess(self, handle: int, code: int) -> int:
            self.terminated = True
            assert code == 0xC0000044
            return 1

        def CloseHandle(self, handle: int) -> int:
            self.closed = True
            return 1

    supervisor = process_limits._WindowsWorkerSupervisor.__new__(process_limits._WindowsWorkerSupervisor)
    kernel = Kernel()
    supervisor._kernel = kernel
    supervisor._handle = 42
    supervisor._cpu_ticks = 10_000_000
    supervisor._stop = threading.Event()
    supervisor.last_cpu_ticks = 0
    supervisor.error = None
    supervisor._supervise()
    should_fail = api_failure or ticks >= 10_000_000
    assert kernel.closed and kernel.terminated is should_fail
    assert (supervisor.error is not None) is should_fail
    if api_failure:
        assert supervisor.error.winerror == 6
    else:
        assert supervisor.last_cpu_ticks == ticks
