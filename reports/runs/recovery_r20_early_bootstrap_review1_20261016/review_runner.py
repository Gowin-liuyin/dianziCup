"""Bounded independent review commands and original-byte evidence receipts."""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
PYTHON = ROOT / "backend/.venv/Scripts/python.exe"
CODE = "abc2c7b50e83c2681f28bbcf35d7f4d014cf096f"
MATERIAL = "4ebfe9a7ae076f3c98d54d72f0b56188350b3efa"
EARLY = "tests/unit/test_r20_early_cpu_bootstrap.py"
ORIGINAL = "tests/unit/test_r20_native_cpu_guard.py"
CBM = ["wsl.exe", "-d", "Ubuntu-22.04", "-u", "root", "--",
       "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp", "cli", "--json"]
PROJECT = "r20_early_bootstrap_review1_src_20261016"
SOURCES = ["backend/src/ai_intel/infrastructure/process_limits.py",
           "backend/src/ai_intel/infrastructure/_worker_bootstrap.py",
           "backend/src/ai_intel/infrastructure/models/semantic.py",
           "backend/src/ai_intel/ingestion/parsing/pdf_text.py",
           "backend/src/ai_intel/ingestion/parsing/_pdf_worker.py",
           "backend/tests/unit/test_r20_early_cpu_bootstrap.py",
           "backend/tests/unit/test_r20_native_cpu_guard.py",
           "backend/tests/unit/test_r20_process_startup.py",
           "backend/tests/unit/test_r04_real_parsing.py", "backend/pyproject.toml",
           "backend/uv.lock", "progress/task_state.json"]
GROUPS = {
    "original_four": (4, [ORIGINAL + "::test_short_cpu_task_keeps_its_result",
        ORIGINAL + "::test_guard_hard_exit_after_readiness_terminates_worker_tree[python-gil-held]",
        ORIGINAL + "::test_guard_hard_exit_after_readiness_terminates_worker_tree[native-gil-held-idle]",
        ORIGINAL + "::test_guard_hard_exit_after_readiness_terminates_worker_tree[native-cpu]"]),
    "product_pdf": (2, ["tests/unit/test_r04_real_parsing.py::test_official_four_pages_have_real_chinese_text_and_exact_page_locator",
        "tests/unit/test_r04_real_parsing.py::test_fake_markers_and_corrupt_inputs_are_not_text_layers[%PDF-1.4\\n%%EOF]"]),
    "semantic": (2, [EARLY + "::test_product_semantic_real_spawn_pipe_accepts_fixture_and_rejects_eof"]),
    "early_short": (1, [EARLY + "::test_fixed_early_spawn_keeps_original_cpu_and_result_boundary[short]"]),
    "early_normal_cpu": (1, [EARLY + "::test_fixed_early_spawn_keeps_original_cpu_and_result_boundary[normal-cpu]"]),
    "body_python_fault": (1, [EARLY + "::test_body_ready_guard_fault_is_additional_to_early_ready_fault[python-gil-held]"]),
    "unready": (1, [str(RUN / "test_review_unready.py")]),
    "pure": (0, ["tests/unit/test_r20_process_startup.py", "tests/unit/test_r05_semantic.py",
        "tests/contract/test_r05_semantic_contract.py::test_model_spaces_pin_source_revision_weights_tokenizer_and_codec",
        "tests/contract/test_r05_semantic_contract.py::test_embedding_domain_result_is_immutable",
        "tests/unit/test_r05_process_limits.py::test_memory_limit_requires_bounded_integer",
        "tests/unit/test_r05_process_limits.py::test_cpu_limit_requires_bounded_integer",
        "tests/unit/test_r05_process_limits.py::test_unsupported_platform_refuses_unbounded_execution",
        "tests/unit/test_r05_process_limits.py::test_pdf_retains_memory_and_cpu_envelope",
        "tests/unit/test_r04_real_parsing.py::test_corrupt_child_protocol_cannot_publish_text",
        "tests/unit/test_r04_real_parsing.py::test_timeout_kills_child_and_releases_capacity_without_passing_secrets",
        "tests/unit/test_r04_real_parsing.py::test_pdf_parser_capacity_and_input_limits_are_explicit",
        EARLY + "::test_fixed_bootstrap_rejects_unlisted_entrypoint_before_launch",
        EARLY + "::test_semantic_result_is_rejected_when_final_supervision_fails",
        EARLY + "::test_real_get_process_times_failure_reports_win32_invalid_handle",
        ORIGINAL + "::test_semantic_worker_retains_two_gib_and_thirty_cpu_seconds",
        str(RUN / "test_review_final_result.py")]),
}


def now() -> str:
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()


def write_json(name: str, value: object) -> None:
    (RUN / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def command(name: str, argv: list[str], cwd: Path | None = None) -> int:
    started, begin = now(), time.monotonic()
    result = subprocess.run(argv, cwd=cwd or ROOT, capture_output=True, check=False)
    (RUN / (name + ".stdout.log")).write_bytes(result.stdout)
    (RUN / (name + ".stderr.log")).write_bytes(result.stderr)
    receipt = {"argv": argv, "cwd": str(cwd or ROOT), "started_at": started, "ended_at": now(),
               "wall_seconds": time.monotonic() - begin, "exit_code": result.returncode,
               "code_sha": CODE, "material_sha": MATERIAL}
    write_json(name + ".command.json", receipt)
    print(json.dumps(receipt))
    print(result.stdout.decode("utf-8", "replace")[:1000])
    print(result.stderr.decode("utf-8", "replace")[:1000])
    return result.returncode


def identity() -> None:
    rows = []
    for path in SOURCES:
        raw = (ROOT / path).read_bytes()
        blob = subprocess.check_output(["git", "show", CODE + ":" + path], cwd=ROOT)
        material = subprocess.check_output(["git", "show", MATERIAL + ":" + path], cwd=ROOT)
        rows.append({"path": path, "raw_sha256": hashlib.sha256(raw).hexdigest(),
                     "code_blob_sha256": hashlib.sha256(blob).hexdigest(),
                     "material_blob_sha256": hashlib.sha256(material).hexdigest(),
                     "code_material_equal": blob == material, "raw_bytes": len(raw),
                     "crlf_count": raw.count(b"\r\n"), "lf_count": raw.count(b"\n"),
                     "raw_matches_code_after_lf_normalization": raw.replace(b"\r\n", b"\n") == blob})
    manifest = ROOT / "reports/runs/recovery_r20_early_cpu_bootstrap_20261016/artifact_manifest.json"
    author = json.loads(manifest.read_text())
    mismatches = []
    for row in author["artifacts"]:
        raw = (ROOT / row["path"]).read_bytes()
        if hashlib.sha256(raw).hexdigest() != row["raw_sha256"] or len(raw) != row["bytes"]:
            mismatches.append(row["path"])
    write_json("source_identity.json", {"checked_at": now(), "code_sha": CODE, "material_sha": MATERIAL,
        "sources": rows, "author_manifest_raw_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
        "author_artifact_count": len(author["artifacts"]), "author_raw_mismatches": mismatches})
    assert len(author["artifacts"]) == 161 and not mismatches
    assert hashlib.sha256(manifest.read_bytes()).hexdigest() == "eb05f8b44d52fcb81fbc022d5565e3674f5ffc302c47b07ab5024ce780bccfe2"
    assert all(row["code_material_equal"] for row in rows)
    print("source and all 161 author raw artifacts verified")


def pytest_group(name: str) -> int:
    from observe_processes import observe

    count, nodes = GROUPS["pure" if name == "pure_config_recheck" else name]
    ledger_path = RUN / "primary_ledger.json"
    ledger = json.loads(ledger_path.read_text()) if ledger_path.exists() else []
    assert sum(row["budgeted_primary_count"] for row in ledger) + count <= 12
    assert not any(row["sample_id"] == name for row in ledger)
    ledger.append({"sample_id": name, "budgeted_primary_count": count, "state": "starting"})
    write_json("primary_ledger.json", ledger)
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(ROOT / "backend/src") + os.pathsep + str(RUN)
    argv = [str(PYTHON), "-B", "-m", "pytest", *nodes, "-v", "-s",
            "-c", str(ROOT / "backend/pyproject.toml"),
            "--junitxml=" + str(RUN / (name + ".xml")),
            "--cov-report=json:" + str(RUN / (name + ".coverage.json")),
            "-o", "cache_dir=" + str(RUN / (name + "_cache")),
            "--basetemp=" + str(RUN / (name + "_temp"))]
    if name == "product_pdf":
        argv += ["-p", "launch_spy"]
    result = observe(name, argv, cwd=ROOT / "backend", run=RUN, environment=environment, timeout=55)
    (RUN / (name + ".stdout.log")).write_text(result["stdout"], encoding="utf-8")
    (RUN / (name + ".stderr.log")).write_text(result["stderr"], encoding="utf-8")
    ledger[-1].update(state="ended", exit_code=result["exit_code"],
                      outer_timeout=result["outer_timeout"], started_at=result["started_at"], ended_at=result["ended_at"],
                      all_observed_signaled=all(row["final"]["signaled"] for row in result["processes"]))
    write_json("primary_ledger.json", ledger)
    return result["exit_code"]


def main() -> None:
    name = sys.argv[1]
    if name == "identity":
        identity()
    elif name == "sync":
        raise SystemExit(command(name, ["uv", "sync", "--locked", "--offline"], ROOT / "backend"))
    elif name == "cbm_help":
        raise SystemExit(command(name, CBM + ["--help"]))
    elif name == "cbm_index":
        raise SystemExit(command(name, CBM + ["index_repository", "--repo-path", "/mnt/d/wt/r20-early-review1/backend/src", "--name", PROJECT, "--mode", "fast", "--persistence", "false"]))
    elif name == "cbm_schema":
        raise SystemExit(command(name, CBM + ["get_graph_schema", "--project", PROJECT, "--format", "json", "--diagnostics", "full"]))
    elif name == "cbm_architecture_recheck":
        raise SystemExit(command(name, CBM + ["get_architecture", "--project", PROJECT, "--aspects", "all", "--format", "json"]))
    elif name.startswith("cbm_trace_"):
        functions = {"limiter": "ai_intel.infrastructure.process_limits.bound_process_resources",
                     "pdf": "ai_intel.ingestion.parsing.pdf_text.parse_pdf_text_layer",
                     "semantic": "ai_intel.infrastructure.models.semantic._run_worker"}
        function = functions[name.removeprefix("cbm_trace_")]
        raise SystemExit(command(name, CBM + ["trace_path", "--project", PROJECT, "--function-name", PROJECT + "." + function, "--direction", "both", "--depth", "3", "--include-evidence", "true", "--format", "json"]))
    elif name == "callers":
        raise SystemExit(command(name, ["rg", "-n", "bound_process_resources|_launch_windows_worker|_WindowsWorkerSupervisor|parse_pdf_text_layer|_EarlySemanticProcess|_run_worker|_bound_worker_memory", "backend/src", "backend/tests", "scripts"]))
    elif name == "diff":
        raise SystemExit(command(name, ["git", "diff", "8a1b04d48346d8550f0326a77f003246a0ebbab5", CODE, "--", "backend/src", "backend/tests"]))
    elif name == "static_ruff":
        raise SystemExit(command(name, [str(PYTHON), "-B", "-m", "ruff", "check", *[str(ROOT / path) for path in SOURCES[:9]]], ROOT / "backend"))
    elif name == "static_format":
        raise SystemExit(command(name, [str(PYTHON), "-B", "-m", "ruff", "format", "--check", *[str(ROOT / path) for path in SOURCES[:9]]], ROOT / "backend"))
    elif name == "static_mypy":
        raise SystemExit(command(name, [str(PYTHON), "-B", "-m", "mypy", "--platform", "win32", *[str(ROOT / path) for path in SOURCES[:4]]], ROOT / "backend"))
    elif name == "diff_check":
        raise SystemExit(command(name, ["git", "diff", "--check"]))
    elif name in GROUPS or name == "pure_config_recheck":
        raise SystemExit(pytest_group(name))
    else:
        raise ValueError(name)


if __name__ == "__main__":
    main()
