"""Real disposable workers exercise CPU timing and native/GIL boundaries without models."""

from __future__ import annotations

import queue
import subprocess
import sys
import threading
import time

import pytest

RESOURCE_SETUP = (
    "from ai_intel.infrastructure.process_limits import bound_process_resources\n"
    "handle=bound_process_resources(memory_bytes=100*1024**2,cpu_seconds=1)\n"
    "print('LIMIT_APPLIED',flush=True)\n"
)


@pytest.mark.parametrize(
    "workload",
    [
        "import sys\nsys.setswitchinterval(60)\nwhile True:\n    pass\n",
        "import hashlib\nhashlib.pbkdf2_hmac('sha256',b'bounded',b'native',100_000_000)\n",
        "import hashlib,threading\n"
        "threads=[threading.Thread(target=hashlib.pbkdf2_hmac,"
        "args=('sha256',b'a',b'b',100_000_000)) for _ in range(2)]\n"
        "for thread in threads: thread.start()\n"
        "for thread in threads: thread.join()\n",
        "import os\nwith open(os.devnull,'wb',buffering=0) as sink:\n"
        "    while True: sink.write(b'bounded kernel operation')\n",
    ],
    ids=["python-gil-held", "native-cpu", "native-two-threads", "kernel-io"],
)
def test_cpu_budget_stops_real_work_without_waiting_for_job_scan(workload: str) -> None:
    started = time.monotonic()
    result = subprocess.run(
        [sys.executable, "-c", RESOURCE_SETUP + workload],
        capture_output=True,
        timeout=3,
        check=False,
    )
    assert b"LIMIT_APPLIED" in result.stdout
    assert result.returncode != 0
    assert b"Traceback" not in result.stderr
    assert time.monotonic() - started < 3


def test_idle_native_call_holding_gil_does_not_spend_cpu_budget() -> None:
    code = (
        RESOURCE_SETUP + "import ctypes,os,time\n"
        "started=time.process_time()\n"
        "if os.name=='nt': ctypes.PyDLL('kernel32').Sleep(1800)\n"
        "else: ctypes.PyDLL(None).usleep(1_800_000)\n"
        "print('IDLE_COMPLETED',time.process_time()-started,flush=True)\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, timeout=8, check=False
    )
    assert result.returncode == 0, result.stderr
    assert b"IDLE_COMPLETED" in result.stdout


def test_short_cpu_task_keeps_its_result() -> None:
    code = RESOURCE_SETUP + "print('RESULT',sum(range(100_000)),flush=True)\n"
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, timeout=8, check=False
    )
    assert result.returncode == 0, result.stderr
    assert b"RESULT 4999950000" in result.stdout


def test_guard_initialization_failure_never_allows_worker_code() -> None:
    code = (
        "import os\n"
        "from ai_intel.infrastructure import process_limits\n"
        "def unavailable(*args,**kwargs): raise OSError('synthetic setup failure')\n"
        "if os.name=='nt': process_limits.subprocess.Popen=unavailable\n"
        "else:\n"
        "    import resource\n"
        "    resource.setrlimit=unavailable\n"
        "try: process_limits.bound_process_resources(memory_bytes=100*1024**2,cpu_seconds=5)\n"
        "except OSError: print('LIMIT_UNAVAILABLE',flush=True)\n"
        "else: print('UNBOUNDED_WORKER',flush=True)\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, timeout=8, check=False
    )
    assert result.returncode == 0, result.stderr
    assert b"LIMIT_UNAVAILABLE" in result.stdout
    assert b"UNBOUNDED_WORKER" not in result.stdout


@pytest.mark.parametrize("caller", ["pdf", "semantic"])
def test_real_product_worker_starts_guard_and_job_cleans_it_on_exit(caller: str) -> None:
    code = (
        "import ctypes,json,os,time\n"
        "from ai_intel.infrastructure import process_limits\n"
        + (
            "from ai_intel.ingestion.parsing._pdf_worker import _bound_memory\n"
            "job_handle=_bound_memory()\n"
            if caller == "pdf"
            else "from ai_intel.infrastructure.models.semantic import _bound_worker_memory\n"
            "_bound_worker_memory()\n"
        )
        + "if os.name=='nt':\n"
        "    assert len(process_limits._WINDOWS_CPU_GUARDS)==1\n"
        "    print('GUARD',process_limits._WINDOWS_CPU_GUARDS[0].pid,flush=True)\n"
        "else: print('NATIVE_RLIMIT',flush=True)\n"
        "time.sleep(0.4)\n"
        "print('WORK_COMPLETED',flush=True)\n"
    )
    with subprocess.Popen(
        [sys.executable, "-c", code], stdout=subprocess.PIPE, stderr=subprocess.PIPE
    ) as worker:
        assert worker.stdout is not None
        ready_lines: queue.Queue[bytes] = queue.Queue()

        def read_ready_line() -> None:
            assert worker.stdout is not None
            ready_lines.put(worker.stdout.readline())

        threading.Thread(target=read_ready_line, daemon=True).start()
        try:
            first_line = ready_lines.get(timeout=8)
        except queue.Empty:
            worker.kill()
            worker.communicate(timeout=1)
            pytest.fail("product worker did not initialize within its existing deadline")
        if first_line.startswith(b"GUARD "):
            import ctypes
            from ctypes import wintypes

            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            kernel.OpenProcess.restype = wintypes.HANDLE
            kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
            kernel.WaitForSingleObject.restype = wintypes.DWORD
            kernel.CloseHandle.argtypes = [wintypes.HANDLE]
            guard_handle = kernel.OpenProcess(0x100000, False, int(first_line.split()[1]))
            assert guard_handle is not None
            try:
                stdout, stderr = worker.communicate(timeout=8)
                assert kernel.WaitForSingleObject(guard_handle, 1000) == 0
            finally:
                kernel.CloseHandle(guard_handle)
        else:
            stdout, stderr = worker.communicate(timeout=8)
            assert first_line == b"NATIVE_RLIMIT\n", stderr
    assert worker.returncode == 0, stderr
    assert b"WORK_COMPLETED" in stdout


def test_failed_guard_readiness_reaps_child_and_closes_setup_handles() -> None:
    code = (
        "import ctypes,gc,os,sys\n"
        "from ai_intel.infrastructure import process_limits\n"
        "if os.name=='nt':\n"
        "    from ctypes import wintypes\n"
        "    kernel=ctypes.WinDLL('kernel32')\n"
        "    kernel.GetCurrentProcess.restype=wintypes.HANDLE\n"
        "    kernel.GetProcessHandleCount.argtypes=[wintypes.HANDLE,ctypes.c_void_p]\n"
        "    def count_handles():\n"
        "        count=wintypes.DWORD()\n"
        "        assert kernel.GetProcessHandleCount("
        "kernel.GetCurrentProcess(),ctypes.byref(count))\n"
        "        return count.value\n"
        "    process_limits.subprocess.run(\n"
        "        [os.path.join(sys.base_prefix,'python.exe'),'-I','-S','-c','pass'],\n"
        "        stdin=process_limits.subprocess.DEVNULL,\n"
        "        stdout=process_limits.subprocess.DEVNULL,\n"
        "        stderr=process_limits.subprocess.DEVNULL,timeout=3,check=True)\n"
        "    gc.collect()\n"
        "    original_popen=process_limits.subprocess.Popen\n"
        "    guards=[]\n"
        "    def record_guard(*args,**kwargs):\n"
        "        guard=original_popen(*args,**kwargs)\n"
        "        guards.append(guard)\n"
        "        return guard\n"
        "    process_limits.subprocess.Popen=record_guard\n"
        "    process_limits._WINDOWS_CPU_GUARD_CODE='import time; time.sleep(20)'\n"
        "    before=count_handles()\n"
        "    try: process_limits.bound_process_resources(memory_bytes=100*1024**2,cpu_seconds=5)\n"
        "    except OSError: pass\n"
        "    else: raise AssertionError('unready guard allowed work')\n"
        "    assert len(guards)==1 and guards[0].poll() is not None\n"
        "    guards.clear()\n"
        "    gc.collect()\n"
        "    after=count_handles()\n"
        "    assert after==before, f'setup handle count {before} -> {after}'\n"
        "else:\n"
        "    try: process_limits._start_windows_cpu_guard(5)\n"
        "    except OSError: pass\n"
        "    else: raise AssertionError('Windows guard started on another platform')\n"
        "print('FAILURE_CLEANED',flush=True)\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, timeout=8, check=False
    )
    assert result.returncode == 0, result.stderr
    assert b"FAILURE_CLEANED" in result.stdout


def test_semantic_worker_retains_two_gib_and_thirty_cpu_seconds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ai_intel.infrastructure import process_limits
    from ai_intel.infrastructure.models import semantic

    observed: list[tuple[int, int]] = []

    def record_limit(*, memory_bytes: int, cpu_seconds: int) -> int:
        observed.append((memory_bytes, cpu_seconds))
        return 42

    monkeypatch.setattr(process_limits, "bound_process_resources", record_limit)
    semantic._bound_worker_memory()
    assert observed == [(2 * 1024**3, 30)]
