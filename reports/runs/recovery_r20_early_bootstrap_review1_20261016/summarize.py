"""Summarize only completed evidence; never launch a worker."""

from __future__ import annotations

import ast
import hashlib
import json
import platform
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from review_runner import CODE, MATERIAL, ROOT, RUN, now, write_json

PRIMARY = {
    "original_four": [(37940, "original-short", 100 * 1024**2, 1, 8),
                      (43532, "original-python-fault", 100 * 1024**2, 1, 8),
                      (34420, "original-idle-fault", 100 * 1024**2, 1, 8),
                      (45404, "original-native-fault", 100 * 1024**2, 1, 8)],
    "product_pdf": [(44864, "official-four-pages", 512 * 1024**2, 15, 20),
                    (44876, "invalid-pdf", 512 * 1024**2, 15, 20)],
    "semantic": [(41520, "synthetic-ok", 2 * 1024**3, 30, 30),
                 (29600, "synthetic-eof", 2 * 1024**3, 30, 30)],
    "early_short": [(3844, "early-short", 100 * 1024**2, 1, 8)],
    "early_normal_cpu": [(14784, "early-normal-cpu", 100 * 1024**2, 1, 8)],
    "body_python_fault": [(43796, "body-python-fault", 100 * 1024**2, 1, 8)],
    "unready": [(42088, "early-unready", 512 * 1024**2, 15, 3)],
}


def main() -> None:
    cases, primaries, commands, owned = [], [], [], []
    query_count = 0
    query_failures = []
    for name in [*PRIMARY, "pure", "pure_config_recheck"]:
        result = json.loads((RUN / (name + ".json")).read_text())
        for stream in ("stdout", "stderr"):
            value = result[stream]
            assert "\ufffd" not in value
            (RUN / (name + "." + stream + ".raw.log")).write_bytes(value.encode("utf-8"))
        tree = ET.parse(RUN / (name + ".xml"))
        selected = []
        for case in tree.getroot().iter("testcase"):
            row = {"run": name, "name": case.attrib["name"], "seconds": float(case.attrib.get("time", 0)),
                   "failed": case.find("failure") is not None, "error": case.find("error") is not None,
                   "skipped": case.find("skipped") is not None}
            cases.append(row)
            selected.append(row)
        coverage_file = RUN / (name + ".coverage.json")
        coverage = json.loads(coverage_file.read_text())["totals"]["percent_covered"] if coverage_file.exists() else None
        command = {key: result[key] for key in ("argv", "cwd", "started_at", "ended_at", "exit_code", "wall_seconds", "outer_timeout", "discovery_errors")}
        command.update(primary_count=len(PRIMARY.get(name, [])),
                       tests=len(selected), passed=sum(not c["failed"] and not c["error"] and not c["skipped"] for c in selected),
                       failed=sum(c["failed"] for c in selected), errors=sum(c["error"] for c in selected),
                       skipped=sum(c["skipped"] for c in selected), coverage_percent=coverage)
        commands.append({"run": name, **command})
        write_json(name + ".command.json", {**command, "code_sha": CODE, "material_sha": MATERIAL})
        by_pid = {process["pid"]: process for process in result["processes"]}
        for pid, sample, memory, cpu, wall in PRIMARY.get(name, []):
            process = by_pid[pid]
            final = process["final"]
            primaries.append({"run": name, "sample": sample, "pid": pid, "parent_pid": process["parent_pid"],
                              "memory_bytes": memory, "cpu_cap_seconds": cpu, "wall_cap_seconds": wall,
                              "creation_ticks": final["creation_ticks"], "exit_ticks": final["exit_ticks"],
                              "kernel_ticks": final["kernel_ticks"], "user_ticks": final["user_ticks"],
                              "actual_cpu_seconds": final["cpu_seconds"],
                              "actual_wall_seconds": (final["exit_ticks"] - final["creation_ticks"]) / 10_000_000,
                              "exit_code": final["process_exit_code"], "signaled": final["signaled"],
                              "get_process_times_success": final["success"], "win32_error": final["win32_error"]})
        for process in result["processes"]:
            owned.append({"run": name, "pid": process["pid"], "parent_pid": process["parent_pid"],
                          "creation_ticks": process["final"]["creation_ticks"], "final": process["final"]})
        for sample in result["samples"]:
            for pid, query in sample["processes"].items():
                query_count += 1
                if not query["success"]:
                    query_failures.append({"run": name, "pid": pid, "query": query})
    assert len(primaries) == 12 and all(row["final"]["signaled"] for row in owned)
    ledger = json.loads((RUN / "primary_ledger.json").read_text())
    assert sum(row["budgeted_primary_count"] for row in ledger) == 12
    assert all(row["state"] == "ended" and row["all_observed_signaled"] and not row["outer_timeout"] for row in ledger)
    allowed = {
        "backend/tests/unit/test_r04_real_parsing.py": {"test_corrupt_child_protocol_cannot_publish_text", "test_timeout_kills_child_and_releases_capacity_without_passing_secrets"},
        "backend/tests/unit/test_r20_process_startup.py": {"test_pdf_parent_filters_coverage_and_unrelated_environment"},
        "backend/tests/unit/test_r20_native_cpu_guard.py": {"test_pdf_parent_rejects_result_missing_after_guard_hard_exit"},
    }
    ast_checks = []
    for path, permitted in allowed.items():
        baseline = subprocess.check_output(["git", "show", "8a1b04d48346d8550f0326a77f003246a0ebbab5:" + path], cwd=ROOT)
        raw = (ROOT / path).read_bytes()
        before, after = ast.parse(baseline), ast.parse(raw)
        before_functions = {node.name: ast.dump(node, include_attributes=False) for node in before.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
        after_functions = {node.name: ast.dump(node, include_attributes=False) for node in after.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
        changed = [name for name in before_functions if before_functions[name] != after_functions.get(name)]
        other_before = [ast.dump(node, include_attributes=False) for node in before.body if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
        other_after = [ast.dump(node, include_attributes=False) for node in after.body if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
        assert set(before_functions) == set(after_functions) and set(changed) == permitted and other_before == other_after
        ast_checks.append({"path": path, "changed_functions": changed, "all_other_ast_identical": True,
                           "baseline_blob_raw_sha256": hashlib.sha256(baseline).hexdigest(),
                           "candidate_checkout_raw_sha256": hashlib.sha256(raw).hexdigest()})
    source_diff = subprocess.check_output(["git", "diff", "--name-status", CODE, MATERIAL, "--", "backend/src", "backend/tests", "backend/pyproject.toml", "backend/uv.lock"], cwd=ROOT)
    assert source_diff == b""
    unique_cases = [row for row in cases if row["run"] != "pure_config_recheck"]
    summary = {"summarized_at": now(), "code_sha": CODE, "material_sha": MATERIAL,
               "python": sys.executable, "version": sys.version, "platform": platform.platform(),
               "commands": commands, "primary_receipts": primaries, "owned_process_instances": owned,
               "tests_all_calls": len(cases), "passed_all_calls": sum(not c["failed"] and not c["error"] and not c["skipped"] for c in cases),
               "failed_all_calls": sum(c["failed"] for c in cases), "skipped_all_calls": sum(c["skipped"] for c in cases),
               "tests_without_redundant_pure_repeat": len(unique_cases),
               "primary_count": len(primaries), "observed_process_count": len(owned), "all_observed_signaled": True,
               "observed_cpu_seconds": sum(row["final"]["cpu_seconds"] for row in owned),
               "sample_wall_sum": sum(row["wall_seconds"] for row in commands), "cpu_query_count": query_count,
               "failed_cpu_queries": query_failures, "test_ast_checks": ast_checks,
               "code_material_backend_diff_empty": True,
               "raw_stdout_note": "Original JSON observer strings are valid UTF-8 with no replacement character; *.raw.log recovers their original CR/LF exactly. Older *.stdout.log is an unchanged derived newline-expanded copy.",
               "limits": ["5ms Toolhelp discovery can miss very short helper processes.", "Process instances are keyed by run/PID/creation ticks, not PID alone.", "Unready one-file pytest invocation did not load the backend coverage configuration and is not an original-gate pass.", "Unready +8 handle baseline is not a proven steady-state leak; no worker rerun was authorized after the 12 cap."]}
    write_json("execution_summary.json", summary)
    print(json.dumps({key: summary[key] for key in ("primary_count", "tests_all_calls", "passed_all_calls", "failed_all_calls", "observed_process_count", "observed_cpu_seconds", "all_observed_signaled", "cpu_query_count")}))


if __name__ == "__main__":
    main()
