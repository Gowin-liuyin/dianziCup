"""Measure one synthetic CLI without changing product code or historical evidence."""

import ast
import ctypes
import hashlib
import importlib.util
import json
import os
import pstats
import subprocess
import sys
import time
from ctypes import wintypes
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path("D:/dianzi")
RUN = Path(__file__).resolve().parent
BASE = Path("C:/Users/yinha/AppData/Roaming/uv/python/cpython-3.12-windows-x86_64-none/python.exe")
INTEGRATION_RUN = ROOT / "reports/runs/recovery_reviewed_integration_20261016"
sys.path.insert(0, str(INTEGRATION_RUN))
import batch13_process_metadata as metadata


def now():
    return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="milliseconds")


def load_limits():
    path = Path("D:/wt/r06-activation-database-fix5-20261017/reports/runs/recovery_r06_activation_prep_20261016/candidate/core/runtime_limits.py")
    spec = importlib.util.spec_from_file_location("diagnosis_owned_job", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.MEMORY_TOTAL = 1024**3
    module.CPU_RATE = max(1, 20000 // os.cpu_count())
    return module, path


def create_synthetic_input():
    source = ROOT / "scripts/annotation/tests/test_prepare.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    body = [
        node
        for node in tree.body
        if (isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id in {"NOW", "QUOTE", "QUOTE_HASH"} for target in node.targets))
        or (isinstance(node, ast.FunctionDef) and node.name == "fixture_bundle")
    ]
    context = {"hashlib": hashlib}
    exec(compile(ast.Module(body=body, type_ignores=[]), str(source), "exec"), context)
    document = context["fixture_bundle"]()
    assert len(document["cases"]) == 1
    assert document["cases"][0]["data_kind"] == "synthetic"
    assert document["cases"][0]["split"] == "dev"
    assert "annotations" not in document
    path = RUN / "synthetic_dev_input.json"
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(document, ensure_ascii=False, indent=2) + "\n")
    return path


def environment():
    values = os.environ.copy()
    for key in tuple(values):
        if key.startswith(("TEST_", "DIANZI_TEST_")) or key in {"DATABASE_URL", "REDIS_URL", "GENERATION_API_KEY", "REVALIDATION_CURSOR_SIGNING_KEY"}:
            values.pop(key)
    values.update(
        APP_ENV="test",
        DATA_MODE="fixture",
        SOURCE_POLLING_ENABLED="false",
        ENRICHMENT_GENERATION_ENABLED="false",
        PYTHONIOENCODING="utf-8",
        PYTHONNOUSERSITE="1",
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONPATH=os.pathsep.join([str(ROOT / "backend/.venv/Lib/site-packages"), str(ROOT / "backend/src"), str(ROOT), str(ROOT / "backend/tests/unit"), str(ROOT / "backend/tests/contract"), str(ROOT / "backend/tests/integration")]),
    )
    return values


def terminate_new_owned(tree, preexisting, supervisor_pid):
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    decisions = []
    for pid, item in reversed(list(tree.items())):
        exact = {"pid": pid, "birth_utc": item["birth_utc"]}
        if pid == supervisor_pid or preexisting.get(pid, {}).get("birth_utc") == item["birth_utc"]:
            decisions.append({**item, "action": "preserve_preexisting_or_supervisor"})
            continue
        try:
            if metadata.identity(pid) != exact:
                continue
        except OSError:
            continue
        handle = kernel.OpenProcess(1, False, pid)
        if handle:
            success = bool(kernel.TerminateProcess(handle, 124))
            decisions.append({**item, "action": "terminate_new_owned", "success": success})
            kernel.CloseHandle(handle)
    return decisions


def main():
    if (RUN / "single_cli.command.json").exists():
        raise RuntimeError("refusing diagnosis evidence overwrite")
    limits, limits_path = load_limits()
    owned_job = limits.OwnedJob()
    start = now()
    start_clock = time.monotonic()
    source_paths = ["scripts/annotation/prepare.py", "scripts/annotation/tests/test_prepare.py", "scripts/annotation/tests/test_prepare_fix1.py", "benchmarks/schemas/candidate_case_v1.json", "scripts/verify_plan.py"]
    source_hashes = {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in source_paths}
    input_path = create_synthetic_input()
    profile_path = RUN / "single_cli.pstats"
    command = [str(BASE), "-B", "-X", "importtime", "-m", "cProfile", "-o", str(profile_path), str(ROOT / "scripts/annotation/prepare.py"), "validate", "--input", str(input_path)]
    control, chain = metadata.control_root(metadata.current_identity())
    preexisting = metadata.descendants(control)
    peak, seen, failure, cleanup = {}, {}, None, []
    samples = []
    with (RUN / "single_cli.stdout.log").open("xb") as stdout, (RUN / "single_cli.stderr.log").open("xb") as stderr:
        child = subprocess.Popen(command, cwd=ROOT / "backend", env=environment(), stdout=stdout, stderr=stderr)
        child_identity = metadata.identity(child.pid)
        while child.poll() is None:
            tree = metadata.descendants(control)
            seen.update(tree)
            if len(tree) > len(peak):
                peak = tree
            samples.append({"elapsed_seconds": time.monotonic() - start_clock, "processes": list(tree.values())})
            if len(tree) > 10:
                failure = "owned_process_limit_exceeded"
            elif time.monotonic() - start_clock >= 20:
                failure = "deadline_exceeded"
            if failure:
                cleanup = terminate_new_owned(tree, preexisting, os.getpid())
                break
            time.sleep(0.02)
        child.wait(timeout=2)
    active = metadata.descendants(control)
    residual = [item for pid, item in active.items() if preexisting.get(pid, {}).get("birth_utc") != item["birth_utc"]]
    result = json.loads((RUN / "single_cli.stdout.log").read_text(encoding="utf-8")) if child.returncode == 0 else None
    expected = child.returncode == 0 and result["human_gold_count"] == 0 and result["formal_evaluation"] == {"status": "not_run", "numerator": None, "denominator": None} and result["annotation_readiness"]["awaiting_human_label"] == 1
    profile = []
    if profile_path.exists():
        stats = pstats.Stats(str(profile_path))
        for (filename, lineno, function), (primitive_calls, calls, self_seconds, cumulative_seconds, callers) in stats.stats.items():
            if filename.endswith("annotation\\prepare.py") or filename.endswith("annotation/prepare.py") or (function == "<module>" and any(name in filename for name in ("jsonschema", "rfc3987_syntax", "lark"))) or ("rfc3987_syntax" in filename and function == "make_syntax_validator") or ("lark.py" in filename and function == "__init__") or function in {"<built-in method posix.waitpid>", "<built-in method _winapi.WaitForSingleObject>"}:
                profile.append({"file": filename, "line": lineno, "function": function, "calls": calls, "self_seconds": self_seconds, "cumulative_seconds": cumulative_seconds})
        profile.sort(key=lambda item: item["cumulative_seconds"], reverse=True)
    (RUN / "single_cli_profile_summary.json").write_text(json.dumps(profile, indent=2) + "\n", encoding="utf-8", newline="\n")
    (RUN / "single_cli_tree_samples.json").write_text(json.dumps(samples, indent=2) + "\n", encoding="utf-8", newline="\n")
    source_stable = all(hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == sha for path, sha in source_hashes.items())
    record = {"started_at": start, "ended_at": now(), "elapsed_seconds": time.monotonic() - start_clock, "command": command, "cwd": str(ROOT / "backend"), "timeout_seconds": 20, "exit_code": child.returncode, "failure": failure, "expected_behavior_matched": expected, "child_identity": child_identity, "windows_peak_count": len(peak), "windows_peak_chain": list(peak.values()), "windows_processes_observed": list(seen.values()), "control_chain": chain, "preexisting_control_processes": list(preexisting.values()), "remaining_owned_processes": residual, "cleanup_decisions": cleanup, "source_hashes": source_hashes, "source_stable": source_stable, "input_sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(), "limits_source": str(limits_path), "limits_source_sha256": hashlib.sha256(limits_path.read_bytes()).hexdigest(), "process_memory_bytes": limits.MEMORY_PER_PROCESS, "job_memory_bytes": limits.MEMORY_TOTAL, "cpu_rate": limits.CPU_RATE, "logical_cpu_count": os.cpu_count(), "job_usage_before_supervisor_exit": owned_job.usage(), "job_scope": "supervisor_and_descendants;tool_ancestors_sampled_separately", "human_gold_count": 0, "test_count": 0, "network_calls": 0, "pg_connections": 0, "wsl_scope": "none", "paid_api_calls": 0, "instrumentation": "cProfile and importtime add overhead; one synthetic direct CLI", "integration": "not_run", "live": "not_run", "manual": "not_run"}
    (RUN / "single_cli.command.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({key: record[key] for key in ("exit_code", "elapsed_seconds", "failure", "expected_behavior_matched", "windows_peak_count", "remaining_owned_processes", "source_stable", "job_usage_before_supervisor_exit")}))
    return int(bool(failure or residual or not expected or not source_stable))


if __name__ == "__main__":
    raise SystemExit(main())
