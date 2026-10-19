"""Validate frozen preparation content and syntax under nine seconds; no PG or secret IO."""

import ast
import ctypes
import hashlib
import importlib.util
import json
import os
import subprocess
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

RUN = Path(__file__).resolve().parent
STARTED = datetime.now(timezone(timedelta(hours=8))).isoformat()
MONOTONIC_START = time.monotonic()
CHECKS = []


def check(name, condition):
    if not condition:
        raise RuntimeError("frozen_preparation_check_failed:" + name)
    CHECKS.append(name)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    spec = importlib.util.spec_from_file_location("frozen_preparation_limits", RUN / "core_runtime_limits.py")
    limits = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(limits)
    limits.MEMORY_TOTAL, limits.CPU_RATE = 1073741824, 20000 // os.cpu_count()
    job = limits.OwnedJob()
    actual = job.query(9, limits.ExtendedLimits)
    actual.basic.flags |= 0x8
    actual.basic.active_limit = 9
    check("native_nine_process_limit", bool(job.kernel.SetInformationJobObject(job.handle, 9, ctypes.byref(actual), ctypes.sizeof(actual))))
    job.kernel.TerminateJobObject.argtypes = [ctypes.c_void_p, ctypes.c_uint]
    watchdog = threading.Timer(9, lambda: job.kernel.TerminateJobObject(job.handle, 124))
    watchdog.daemon = True
    watchdog.start()
    try:
        manifest_path = RUN / "launch_bindings.json"
        bindings = json.loads(manifest_path.read_bytes())
        manifest_sha = digest(manifest_path)
        check("three_exact_packets", len(bindings["packets"]) == 3)
        check("unchanged_budget", bindings["resource_caps"] == {"target": 2, "sampler": 1,
              "process_memory": 536870912, "job_memory": 1073741824, "cpu_cores": 2,
              "native_process": 9, "full_windows": 10})
        check("unchanged_deadline", bindings["deadline"] == {"controller_seconds": 58, "child_cutoff_seconds": 48, "root_outer_seconds": 60})
        check("source_oid_identity_only", bindings["source_oids_identity_only"] == [10451302, 10434264])
        unique_inputs = {}
        for packet in bindings["packets"]:
            for item in packet["frozen_files"]:
                path = Path(item["path"])
                check("source_raw:" + str(path), digest(path) == item["raw_sha256"])
                check("source_mtime:" + str(path), str(path.stat().st_mtime_ns) == item["mtime_ns"])
                unique_inputs[str(path)] = item
            document = json.loads(Path(packet["packet_path"]).read_bytes())
            admission = json.loads(Path(packet["admission_path"]).read_bytes())
            check("schema_source:" + packet["source_sha"], document["source_sha"] == packet["source_sha"] == admission["source_sha"])
            check("schema_controller:" + packet["source_sha"], digest(Path(packet["controller_path"])) == document["controller_raw_sha256"])
            check("schema_admission:" + packet["source_sha"], digest(Path(packet["admission_path"])) == document["admission_raw_sha256"])
            check("schema_authority:" + packet["source_sha"], document["root_required_environment"]["DIANZI_REVIEW_RESOURCE_AUTHORIZED"] == packet["authority_header"])
            check("schema_whitelist:" + packet["source_sha"], document["allowed_labels"] == list(packet["groups"]))
            plan = json.loads((Path(packet["support_root"]) / "pg_batch_plan.json").read_bytes())
            check("exact_case_counts:" + packet["source_sha"], [(g["label"], len(g["nodes"]), g["expected_cases"]) for g in plan["groups"]] ==
                  [(label, count, count) for label, count in packet["groups"].items()])
        check("qa19_r10_4_r16_13", [sum(p["groups"].values()) for p in bindings["packets"]] == [19, 4, 13])
        migrations = json.loads((RUN / "migration_compatibility.json").read_bytes())
        check("93_full_migration_comparisons", len(migrations["records"]) == 93)
        for item in migrations["records"]:
            root_raw = Path(item["root"]["path"]).read_bytes()
            source_raw = Path(item["source"]["path"]).read_bytes()
            check("migration_raw_frozen:" + item["worktree"] + ":" + item["file"],
                  hashlib.sha256(root_raw).hexdigest() == item["root"]["raw_sha256"] and
                  hashlib.sha256(source_raw).hexdigest() == item["source"]["raw_sha256"])
            check("migration_whole_ast:" + item["worktree"] + ":" + item["file"],
                  ast.dump(ast.parse(root_raw), include_attributes=False) == ast.dump(ast.parse(source_raw), include_attributes=False))
            check("migration_normalized_raw:" + item["worktree"] + ":" + item["file"],
                  root_raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n") == source_raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n"))
        mother_path = Path("D:/wt/r18-ports-review1/reports/runs/r18_plugin_production_ports_review1_20261017/pg_support")
        mother_controller = ast.parse((mother_path / "run_pg_review.py").read_bytes())
        own_controller = ast.parse((RUN / "r16_pg_support/run_pg_review.py").read_bytes())
        check("controller_all_original_assertions_unchanged", [ast.dump(n, include_attributes=False) for n in ast.walk(mother_controller) if isinstance(n, ast.Assert)] ==
              [ast.dump(n, include_attributes=False) for n in ast.walk(own_controller) if isinstance(n, ast.Assert)])
        for name in ("batch13_process_metadata.py", "core_runtime_limits.py", "parent_lock_observation.py",
                     "pg_phase_plugin.py", "process_identity.py", "worker_entry.py", "task_migration_entry.py"):
            check("byte_exact_mother_helper:" + name, (mother_path / name).read_bytes() == (RUN / "r16_pg_support" / name).read_bytes())
        template = (RUN / "launch_root_pg_packet.template.ps1").read_bytes()
        launcher = (RUN / "launch_root_pg_packet.ps1").read_bytes()
        check("launcher_exact_sealed_template", launcher == template.replace(b"__BINDINGS_RAW_SHA256__", manifest_sha.encode()))
        check("launcher_no_shell_eval", b"Invoke-Expression" not in launcher and b"nestedCommand" not in launcher and b"ArgumentList.Add" in launcher)
        check("launcher_empty_child_environment", b"$info.Environment.Clear()" in launcher)
        python_files = sorted(RUN.rglob("*.py"))
        for path in python_files:
            ast.parse(path.read_bytes(), filename=str(path))
            CHECKS.append("syntax_only:" + str(path.relative_to(RUN)))
        argv = ["C:/Users/yinha/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/powershell/pwsh.exe",
                "-NoLogo", "-NoProfile", "-File", str(RUN / "syntax_only.ps1")]
        result = subprocess.run(argv, capture_output=True, timeout=max(0.1, 8.5 - (time.monotonic() - MONOTONIC_START)),
                env={"SystemRoot": "C:/Windows", "WINDIR": "C:/Windows", "PATH": "C:/Windows/System32", "TEMP": str(RUN), "TMP": str(RUN)})
        (RUN / "verify_syntax.stdout.log").write_bytes(result.stdout)
        (RUN / "verify_syntax.stderr.log").write_bytes(result.stderr)
        check("powershell_syntax_only", result.returncode == 0)
        receipt = {"started_at": STARTED, "ended_at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
            "elapsed_seconds": time.monotonic() - MONOTONIC_START, "exit_code": 0, "native_seconds": 9, "outer_seconds": 10,
            "source_unique_files": len(unique_inputs), "check_count": len(CHECKS), "checks": CHECKS,
            "python_syntax_files": len(python_files), "powershell_syntax_argv": argv, "powershell_syntax_exit_code": result.returncode,
            "business_tests_executed": 0, "pg_connected": False, "secrets_read": False,
            "job_limits": {"process_memory_bytes": 536870912, "job_memory_bytes": 1073741824,
                "native_active_cap": 9, "logical_cpu_max": 2, "usage": job.usage()},
            "launch_bindings_raw_sha256": manifest_sha, "launcher_raw_sha256": digest(RUN / "launch_root_pg_packet.ps1")}
        (RUN / "verification_receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (RUN / "input_manifest.json").write_text(json.dumps({"frozen_at": STARTED, "files": list(unique_inputs.values())}, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"exit_code": 0, "elapsed_seconds": receipt["elapsed_seconds"], "check_count": len(CHECKS),
                          "source_unique_files": len(unique_inputs), "business_tests_executed": 0, "pg_connected": False}))
    finally:
        watchdog.cancel()


if __name__ == "__main__":
    main()
