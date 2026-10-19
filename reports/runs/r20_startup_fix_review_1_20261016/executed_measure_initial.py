"""Three explicit samples pair real resource enforcement with startup and protocol observations."""

from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path

from observe_review import DescendantObserver

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent


def observe(name: str, code: str, *, coverage: bool, content: bytes = b"") -> dict[str, object]:
    environment = os.environ.copy()
    if coverage:
        environment.update(COV_CORE_SOURCE="ai_intel", COV_CORE_CONFIG=";", COV_CORE_DATAFILE=str(RUN / f".{name}.coverage"))
    record = {"sample_id": name, "explicit_synthetic_harness": True, "coverage_requested": coverage, "worker_code": code, "ready_deadline_seconds": 8, "wall_deadline_seconds": 20, "async_stdin": True}
    events: queue.Queue[tuple[float, bytes]] = queue.Queue()
    lines: list[str] = []
    started = time.monotonic()
    with DescendantObserver() as observer:
        observer.current_case = name
        worker = subprocess.Popen([sys.executable, "-B", "-c", code], env=environment, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=0x08000000)

        def writer() -> None:
            try:
                worker.stdin.write(content)
            except BrokenPipeError:
                pass
            finally:
                worker.stdin.close()

        def reader() -> None:
            for line in iter(worker.stdout.readline, b""):
                events.put((time.monotonic(), line))
            events.put((time.monotonic(), b""))

        writing = threading.Thread(target=writer, daemon=True)
        reading = threading.Thread(target=reader, daemon=True)
        writing.start()
        reading.start()
        try:
            while True:
                received, line = events.get(timeout=max(0.001, started + 8 - time.monotonic()))
                if line:
                    lines.append(line.decode("utf-8"))
                if line.startswith(b"READY "):
                    record["ready_wall_seconds"] = received - started
                    break
                if not line:
                    record["exited_before_ready"] = True
                    break
            worker.wait(timeout=max(0.001, started + 20 - time.monotonic()))
            reading.join(timeout=1)
            writing.join(timeout=1)
            while not events.empty():
                received, line = events.get_nowait()
                if line:
                    lines.append(line.decode("utf-8"))
        finally:
            if worker.poll() is None:
                worker.kill()
                worker.wait(timeout=1)
            record.update(exit_code=worker.returncode, stdout="".join(lines), stderr=worker.stderr.read().decode("utf-8", errors="replace"), wall_seconds=time.monotonic() - started)
            worker.stdout.close()
            worker.stderr.close()
    record.update(processes=list(observer.records.values()), observed_cpu_seconds=sum(row["final_cpu"]["total_cpu_seconds"] for row in observer.records.values()), all_observed_processes_signaled=all(row["signaled"] for row in observer.records.values()))
    (RUN / f"{name}.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in record.items() if key not in {"stdout", "stderr", "worker_code", "processes"}}), flush=True)
    return record


def semantic_control(connection: object, *arguments: object) -> None:
    from ai_intel.infrastructure import process_limits
    from ai_intel.infrastructure.models import semantic

    events = [{"stage": "entry_after_site", "cpu": time.process_time(), "monotonic": time.monotonic()}]
    original_bound = semantic._bound_worker_memory
    bound = False

    def observed_bound() -> None:
        nonlocal bound
        original_bound()
        bound = True
        events.append({"stage": "after_bound", "cpu": time.process_time(), "monotonic": time.monotonic()})

    def verified(*args: object) -> Path:
        assert bound
        events.append({"stage": "synthetic_artifact_verification", "cpu": time.process_time(), "monotonic": time.monotonic()})
        return RUN

    def infer(*args: object) -> object:
        assert bound
        import coverage

        record = {"sample_id": "semantic_coverage_positive", "fixture": True, "coverage_active": coverage.Coverage.current() is not None, "synthetic_inference": True, "actual_worker_function": "semantic._semantic_worker", "events": events, "worker_pid": os.getpid(), "guardian_pid": process_limits._WINDOWS_CPU_GUARDS[0].pid, "no_runtime_imported": all(name not in sys.modules for name in ("onnxruntime", "numpy", "tokenizers")), "memory_limit_bytes": 2 * 1024**3, "cpu_limit_seconds": 30}
        (RUN / "semantic_coverage_worker.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        return [[1.0] + [0.0] * 383]

    semantic._bound_worker_memory = observed_bound
    semantic._verified_model_directory = verified
    semantic._infer_local = infer
    semantic._semantic_worker(connection, *arguments)


def main() -> None:
    mark = "import os,time,json\ndef mark(stage): print('OBS',json.dumps([stage,os.getpid(),time.monotonic(),time.process_time()]),flush=True)\nmark('entry_after_site')\n"
    exhausted = observe("initial_cpu_exhausted", mark + "from ai_intel.infrastructure import process_limits as limits\nwith open(os.devnull,'wb',buffering=0) as stream:\n    while time.process_time()<1.1: stream.write(b'bounded kernel operation')\nmark('before_bound')\nhandle=limits.bound_process_resources(memory_bytes=100*1024**2,cpu_seconds=1)\nprint('READY',flush=True)\nprint('FORBIDDEN_SUCCESS',flush=True)\n", coverage=False)
    assert exhausted.get("exited_before_ready") and "FORBIDDEN_SUCCESS" not in exhausted["stdout"]
    assert exhausted["all_observed_processes_signaled"]
    pdf_code = mark + "import builtins\nfrom ai_intel.ingestion.parsing import _pdf_worker as worker\nmark('after_module_import')\noriginal_bound=worker._bound_memory\nbound=False\ndef observed_bound():\n    global bound\n    result=original_bound()\n    bound=True\n    mark('after_bound')\n    print('READY',flush=True)\n    return result\nworker._bound_memory=observed_bound\noriginal_import=builtins.__import__\nfirst=True\ndef observed_import(name,*args,**kwargs):\n    global first\n    if name.startswith('pypdf'):\n        assert bound\n        if first:\n            first=False\n            mark('before_heavy_import')\n            result=original_import(name,*args,**kwargs)\n            mark('after_heavy_import')\n            return result\n    return original_import(name,*args,**kwargs)\nbuiltins.__import__=observed_import\nworker.main()\n"
    pdf = observe("pdf_coverage_async", pdf_code, coverage=True, content=(ROOT / "docs/references/competition_brief.pdf").read_bytes())
    assert pdf["exit_code"] == 0 and pdf["ready_wall_seconds"] < 8 and pdf["all_observed_processes_signaled"]
    assert len(json.loads(pdf["stdout"].splitlines()[-1])["pages"]) == 4
    from ai_intel.infrastructure.models import semantic

    environment_before = {key: os.environ.get(key) for key in ("COV_CORE_SOURCE", "COV_CORE_CONFIG", "COV_CORE_DATAFILE")}
    os.environ.update(COV_CORE_SOURCE="ai_intel", COV_CORE_CONFIG=";", COV_CORE_DATAFILE=str(RUN / ".semantic_coverage_positive.coverage"))
    original_worker = semantic._semantic_worker
    cache = RUN / "synthetic_model_placeholder"
    cache.mkdir(exist_ok=True)
    started = time.monotonic()
    try:
        semantic._semantic_worker = semantic_control
        with DescendantObserver() as observer:
            observer.current_case = "semantic_coverage_positive"
            result = semantic.LocalSemanticModels(cache).embed_query("explicit synthetic protocol control")
    finally:
        semantic._semantic_worker = original_worker
        for key, value in environment_before.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    assert result.vectors == ((1.0,) + (0.0,) * 383,)
    worker_record = json.loads((RUN / "semantic_coverage_worker.json").read_text(encoding="utf-8"))
    assert worker_record["coverage_active"] and worker_record["no_runtime_imported"]
    record = {"sample_id": "semantic_coverage_positive", "fixture": True, "synthetic_result": True, "real_spawn_pipe_actual_worker": True, "wall_seconds": time.monotonic() - started, "processes": list(observer.records.values()), "observed_cpu_seconds": sum(row["final_cpu"]["total_cpu_seconds"] for row in observer.records.values()), "all_observed_processes_signaled": all(row["signaled"] for row in observer.records.values())}
    assert record["all_observed_processes_signaled"]
    (RUN / "semantic_coverage_positive.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in record.items() if key != "processes"}), flush=True)


if __name__ == "__main__":
    main()
