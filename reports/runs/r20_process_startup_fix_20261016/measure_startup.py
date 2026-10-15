"""Three sequential diagnostic scenarios; synthetic semantic output is explicitly marked."""

from __future__ import annotations

import datetime
import json
import os
import queue
import subprocess
import sys
import threading
import time
from multiprocessing.connection import Connection
from pathlib import Path

from observe_boundaries import cpu_snapshot, kernel

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent


def observe(name: str, code: str, *, coverage: bool, content: bytes = b"") -> dict[str, object]:
    environment = os.environ.copy()
    for key in tuple(environment):
        if key.startswith("COV_CORE_") or key.startswith("COVERAGE_PROCESS_"):
            del environment[key]
    if coverage:
        environment.update(
            COV_CORE_SOURCE="ai_intel",
            COV_CORE_CONFIG=";",
            COV_CORE_DATAFILE=str(RUN / f".{name}.coverage"),
        )
    record: dict[str, object] = {
        "fixture": True,
        "name": name,
        "coverage": coverage,
        "worker_code": code,
        "started_at": datetime.datetime.now().astimezone().isoformat(),
        "ready_deadline_seconds": 8,
        "outer_wall_deadline_seconds": 20,
        "ready_reader_has_async_input": True,
    }
    handles: list[int] = []
    events: queue.Queue[bytes] = queue.Queue()
    lines: list[str] = []
    started = time.monotonic()
    record["launch_monotonic"] = started
    with subprocess.Popen(
        [sys.executable, "-B", "-c", code],
        env=environment,
        cwd=ROOT / "backend",
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ) as worker:
        assert worker.stdout is not None and worker.stdin is not None

        def write_input() -> None:
            assert worker.stdin is not None
            try:
                worker.stdin.write(content)
            except BrokenPipeError:
                pass
            finally:
                worker.stdin.close()

        writer = threading.Thread(target=write_input, daemon=True)
        writer.start()

        def read_lines() -> None:
            assert worker.stdout is not None
            for line in iter(worker.stdout.readline, b""):
                events.put(line)
            events.put(b"")

        reader = threading.Thread(target=read_lines, daemon=True)
        reader.start()
        try:
            ready_deadline = started + 8
            while True:
                line = events.get(timeout=max(0.001, ready_deadline - time.monotonic()))
                lines.append(line.decode("utf-8", errors="replace"))
                if line.startswith(b"OBS ") and not handles:
                    pid = json.loads(line[4:])[1]
                    handle = kernel.OpenProcess(0x100000 | 0x1000 | 0x1, False, pid)
                    if not handle:
                        raise RuntimeError("worker query handle unavailable")
                    handles.append(handle)
                    record["worker_pid"] = pid
                if line.startswith(b"GUARD ") or line.startswith(b"READY "):
                    pid = int(line.split()[1])
                    handle = kernel.OpenProcess(0x100000 | 0x1000 | 0x1, False, pid)
                    if handle:
                        handles.append(handle)
                    record["guardian_pid"] = pid
                if line.startswith(b"READY "):
                    record["ready_wall_seconds"] = time.monotonic() - started
                    record["ready_cpu"] = [cpu_snapshot(handle) for handle in handles]
                    break
                if not line:
                    record["exited_before_readiness"] = True
                    break
            worker.wait(timeout=max(0.001, started + 20 - time.monotonic()))
            writer.join(timeout=1)
            reader.join(timeout=1)
            while not events.empty():
                line = events.get_nowait()
                if line:
                    lines.append(line.decode("utf-8", errors="replace"))
            record["exit_code"] = worker.returncode
        except BaseException as error:
            record["observation_error"] = repr(error)
            for handle in handles:
                if kernel.WaitForSingleObject(handle, 0) != 0:
                    kernel.TerminateProcess(handle, 0xC0000044)
            if worker.poll() is None:
                worker.kill()
                worker.wait(timeout=1)
        finally:
            assert worker.stderr is not None
            record.update(
                stdout="".join(lines),
                stderr=worker.stderr.read().decode("utf-8", errors="replace"),
                final_cpu=[cpu_snapshot(handle) for handle in handles],
                tree_signaled=[kernel.WaitForSingleObject(handle, 1000) == 0 for handle in handles],
                wall_seconds=time.monotonic() - started,
                ended_at=datetime.datetime.now().astimezone().isoformat(),
            )
            for handle in handles:
                kernel.CloseHandle(handle)
            (RUN / f"{name}.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    print(json.dumps(record, ensure_ascii=False), flush=True)
    return record


def semantic_control_worker(connection: Connection, *arguments: object) -> None:
    from ai_intel.infrastructure import process_limits
    from ai_intel.infrastructure.models import semantic

    semantic._bound_worker_memory()
    (RUN / "semantic_control_worker.json").write_text(
        json.dumps(
            {
                "fixture": True,
                "pid": os.getpid(),
                "guardian_pid": process_limits._WINDOWS_CPU_GUARDS[0].pid,
                "start_method": "spawn",
                "cpu_seconds_limit": 30,
                "memory_bytes": 2 * 1024**3,
                "coverage_active": "coverage" in sys.modules,
                "runtime_imported": "onnxruntime" in sys.modules,
                "cpu_seconds_before_send": time.process_time(),
                "synthetic_output": True,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    connection.send(("ok", [[1.0] + [0.0] * 383]))
    connection.close()


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    mark = (
        "import os,time,json\n"
        "def mark(stage): print('OBS',json.dumps([stage,os.getpid(),time.monotonic(),"
        "time.process_time()]),flush=True)\nmark('entry_after_site')\n"
    )
    exhausted = observe(
        "initial_budget_exhausted",
        mark
        + (
            "from ai_intel.infrastructure import process_limits as limits\n"
            "with open(os.devnull,'wb',buffering=0) as sink:\n"
            "    while time.process_time()<1.1: sink.write(b'bounded kernel operation')\n"
            "mark('before_bound')\n"
            "original=limits.subprocess.Popen\n"
            "def launch(*args,**kwargs):\n"
            "    guard=original(*args,**kwargs)\n"
            "    print('GUARD',guard.pid,flush=True)\n"
            "    return guard\n"
            "limits.subprocess.Popen=launch\n"
            "handle=limits.bound_process_resources(memory_bytes=100*1024**2,cpu_seconds=1)\n"
            "print('READY',limits._WINDOWS_CPU_GUARDS[0].pid,flush=True)\n"
            "print('RESULT_AFTER_EXHAUSTION',flush=True)\n"
        ),
        coverage=False,
    )
    assert exhausted.get("exited_before_readiness") is True
    assert "RESULT_AFTER_EXHAUSTION" not in exhausted["stdout"]
    assert "observation_error" not in exhausted
    assert all(exhausted["tree_signaled"])
    pdf = observe(
        "pdf_coverage_after_fix",
        mark
        + (
            "import builtins\nfrom ai_intel.infrastructure import process_limits\n"
            "from ai_intel.ingestion.parsing import _pdf_worker as worker\n"
            "mark('after_pdf_module_import')\n"
            "original_bound=worker._bound_memory\n"
            "def observed_bound():\n"
            "    mark('before_bound')\n"
            "    handle=original_bound()\n"
            "    mark('after_bound')\n"
            "    print('READY',process_limits._WINDOWS_CPU_GUARDS[0].pid,flush=True)\n"
            "    return handle\n"
            "worker._bound_memory=observed_bound\n"
            "original_import=builtins.__import__\n"
            "first=True\n"
            "def observed_import(name,*args,**kwargs):\n"
            "    global first\n"
            "    if first and name.startswith('pypdf'):\n"
            "        first=False\n"
            "        mark('before_heavy_import')\n"
            "        result=original_import(name,*args,**kwargs)\n"
            "        mark('after_heavy_import')\n"
            "        return result\n"
            "    return original_import(name,*args,**kwargs)\n"
            "builtins.__import__=observed_import\nworker.main()\n"
        ),
        coverage=True,
        content=(ROOT / "docs/references/competition_brief.pdf").read_bytes(),
    )
    assert pdf["exit_code"] == 0 and pdf["ready_wall_seconds"] < 8
    assert "observation_error" not in pdf and all(pdf["tree_signaled"])
    assert len(json.loads(pdf["stdout"].splitlines()[-1])["pages"]) == 4
    from ai_intel.infrastructure.models import semantic

    original_worker = semantic._semantic_worker
    semantic._semantic_worker = semantic_control_worker
    cache = Path("D:/tmp/r20-process-startup-fix-model-placeholder")
    cache.mkdir(parents=True, exist_ok=True)
    began = time.monotonic()
    try:
        result = semantic.LocalSemanticModels(cache).embed_query("bounded")
    finally:
        semantic._semantic_worker = original_worker
    assert result.vectors == ((1.0,) + (0.0,) * 383,)
    summary = {
        "fixture": True,
        "real_spawn_pipe": True,
        "synthetic_model_output": True,
        "wall_seconds": time.monotonic() - began,
        "dimensions": len(result.vectors[0]),
    }
    (RUN / "semantic_positive_control.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()
