"""Independent frozen-code receipts, manifest checks and src-only CLI preparation."""

from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
PREP = ROOT / "reports/runs/recovery_r06_incremental_observation_preparation_20261016"
PYTHON = "D:/dianzi/backend/.venv/Scripts/python.exe"
CODE = "1c4cce9770bfa29d08728a0131f7fc7fe714f9bc"
MATERIAL = "521b740612b2d0465f2be50cd58b5028f1c820b7"
HEAD = "b08824f738ca185776916ae02689d8507f956c5c"
CBM = "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp"
SRC_WSL = "/mnt/d/wt/r06-recheck/reports/runs/recovery_r06_observer_newreview_recheck_20261016/cbm_source"
WSL = ["wsl.exe", "-d", "Ubuntu-22.04", "-u", "root", "--", CBM]


def now() -> str:
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def save(name: str, value: object) -> None:
    (RUN / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def manifest() -> None:
    raw = (PREP / "artifact_manifest_fix1.json").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == "b797ea19c6bb4f60373fbb8b9fced1111ab207a4eca34342f4b95a3bc0b27f46"
    value = json.loads(raw)
    assert value["schema"] == "observer-fix1-artifact-manifest-v2"
    assert value["code_sha"] == CODE and value["prior_material_sha"] == "6957be2aa68139f17e02186169428123a2fa37c1"
    assert value["review_manifest_body_sha256"] == "adef785ee9fbb5f3783945af095327ff455a4e8f3941a6a6de8e9a27c415ae37"
    assert value["unit_tests"] == {"passed": 32, "total": 32, "failed": 0, "skipped": 0}
    assert value["original_red"] == {"records": 21, "passed": 15, "failed": 6, "original_script_bytes_preserved": True}
    assert value["gates"] == {"total_bytes": 16777216, "snapshot_bytes": 1048576, "maximum_record_bytes": 1056768}
    assert value["new_live_seconds"] == 0 and value["root_live_gate_present"] is False
    tree = subprocess.check_output(["git", "ls-tree", "-rz", "--full-tree", MATERIAL], cwd=ROOT)
    fixed = {}
    for entry in tree.split(b"\0"):
        if entry:
            info, name = entry.split(b"\t", 1)
            fixed[name.decode()] = info.split()[2].decode()
    records = []
    assert len(value["artifacts"]) == 150
    for item in value["artifacts"]:
        assert set(item) == {"path", "working_tree_bytes", "working_tree_sha256", "git_blob_oid", "git_blob_bytes", "git_blob_content_sha256", "working_tree_equals_git_blob"}
        local = ROOT / item["path"]
        assert local.resolve().is_relative_to(ROOT) and local.is_file()
        assert fixed[item["path"]] == item["git_blob_oid"]
        blob = subprocess.check_output(["git", "cat-file", "blob", item["git_blob_oid"]], cwd=ROOT)
        content = local.read_bytes()
        assert (len(blob), hashlib.sha256(blob).hexdigest()) == (item["git_blob_bytes"], item["git_blob_content_sha256"])
        assert (len(content), hashlib.sha256(content).hexdigest()) == (item["working_tree_bytes"], item["working_tree_sha256"])
        assert (content == blob) is item["working_tree_equals_git_blob"]
        records.append({"path": item["path"], "tree_oid": fixed[item["path"]], "working_tree_equal": content == blob, "passed": True})
    original = Path("D:/wt/r06-newrev/reports/runs/recovery_r06_observer_newreview_20261016")
    original_manifest = (original / "artifact_manifest.json").read_bytes()
    assert hashlib.sha256(original_manifest).hexdigest() == value["review_manifest_body_sha256"]
    original_state = json.loads(original_manifest)
    for item in original_state["artifacts"]:
        content = (original.parents[2] / item["path"]).read_bytes()
        assert (len(content), hashlib.sha256(content).hexdigest()) == (item["bytes"], item["sha256"])
    retained = (PREP / "original_negative_probes.py.txt").read_bytes()
    assert retained == (original / "negative_probes.py").read_bytes()
    old_manifest_blob = subprocess.check_output(["git", "show", "6957be2aa68139f17e02186169428123a2fa37c1:" + (PREP / "artifact_manifest.json").relative_to(ROOT).as_posix()], cwd=ROOT)
    assert old_manifest_blob == (PREP / "artifact_manifest.json").read_bytes()
    tests = {}
    for name in ("test_observation_log.py", "test_pg_snapshot.py"):
        old = subprocess.check_output(["git", "show", "6957be2aa68139f17e02186169428123a2fa37c1:" + (PREP / name).relative_to(ROOT).as_posix()], cwd=ROOT)
        names_old = {node.name for node in ast.walk(ast.parse(old.decode())) if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")}
        names_now = {node.name for node in ast.walk(ast.parse((PREP / name).read_text(encoding="utf-8"))) if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")}
        assert names_now == names_old
        tests[name] = len(names_now)
    save("manifest_check.json", {"recorded_at": now(), "manifest_body_sha256": hashlib.sha256(raw).hexdigest(), "material_sha": MATERIAL, "head_sha": HEAD, "fixed_blobs_passed": 150, "working_tree_passed": 150, "declared_differences": [item["path"] for item in records if not item["working_tree_equal"]], "original_review_artifact_hashes_unchanged": len(original_state["artifacts"]), "retained_original_probe_sha256": hashlib.sha256(retained).hexdigest(), "original_22_test_names_preserved": tests, "artifacts": records})
    print(json.dumps({"fixed_blobs": 150, "working_tree": 150, "original_artifacts_unchanged": len(original_state["artifacts"]), "original_tests": tests}))


def copy_source() -> None:
    files = subprocess.check_output(["git", "ls-tree", "-rz", "--full-tree", "349c5e3ec27196257b98cdfcb63c75fb50157978", "--", "backend/src"], cwd=ROOT)
    copy = RUN / "cbm_source"
    assert not copy.exists()
    receipts = []
    for item in files.split(b"\0"):
        if not item:
            continue
        info, path = item.split(b"\t", 1)
        relative = path.decode()
        body = (ROOT / relative).read_bytes()
        blob = subprocess.check_output(["git", "cat-file", "blob", info.split()[2].decode()], cwd=ROOT)
        assert body.replace(b"\r\n", b"\n") == blob.replace(b"\r\n", b"\n")
        output = copy / Path(relative).relative_to("backend/src")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(blob)
        receipts.append({"path": relative, "git_blob_sha256": hashlib.sha256(blob).hexdigest(), "copy_relative": output.relative_to(RUN).as_posix(), "bytes": len(blob)})
    save("source_copy_receipt.json", {"recorded_at": now(), "base": "349c5e3ec27196257b98cdfcb63c75fb50157978", "src_only": True, "files": receipts})
    print(json.dumps({"src_files": len(receipts), "path": str(copy)}))


def command(name: str) -> None:
    target = PREP.relative_to(ROOT).as_posix()
    owned_python = str(RUN / "runtime_env/.venv/Scripts/python.exe")
    commands = {
        "ruff": [PYTHON, "-B", "-m", "ruff", "check", "--config", "backend/pyproject.toml", target],
        "format": [PYTHON, "-B", "-m", "ruff", "format", "--check", "--config", "backend/pyproject.toml", target],
        "mypy": [PYTHON, "-B", "-m", "mypy", "--follow-imports=silent", "--disallow-untyped-defs", *[f"{target}/{file}" for file in ("observation_log.py", "pg_snapshot.py", "observe.py", "replay_old_run.py", "verify_preparation.py", "review_fix1_probes.py")]],
        "unit32": [PYTHON, "-B", "-m", "unittest", "discover", "-s", target, "-p", "test_*.py", "-v"],
        "absent_gate": [PYTHON, "-B", str(PREP / "observe.py")],
        "independent21": [PYTHON, "-B", str(RUN / "independent_probes.py")],
        "boundaries_sources": [PYTHON, "-B", str(RUN / "boundary_and_sources.py")],
        "boundaries_sources_retry2": [PYTHON, "-B", str(RUN / "boundary_and_sources.py")],
        "cbm_help": WSL + ["--help"],
        "cbm_index_help": WSL + ["cli", "index_repository", "--help"],
        "cbm_schema_help": WSL + ["cli", "get_graph_schema", "--help"],
        "cbm_index": WSL + ["cli", "--json", "index_repository", "--repo-path", SRC_WSL, "--mode", "fast", "--name", "r06_observer_recheck_src", "--persistence", "true"],
        "cbm_schema": WSL + ["cli", "--json", "get_graph_schema", "--project", "r06_observer_recheck_src", "--format", "json", "--diagnostics", "full", "--limit", "15"],
        "cbm_search": WSL + ["cli", "--json", "search_graph", "--project", "r06_observer_recheck_src", "--name-pattern", "enqueue_source_page|enqueue_due_source_collections|commit_page|build_source_page_handler|execute_job|enqueue_job", "--format", "json", "--limit", "20", "--max-output-tokens", "5000"],
        "cbm_search_enqueue": WSL + ["cli", "--json", "search_graph", "--project", "r06_observer_recheck_src", "--name-pattern", "enqueue_source_page", "--format", "json", "--limit", "5"],
        "cbm_search_commit": WSL + ["cli", "--json", "search_graph", "--project", "r06_observer_recheck_src", "--name-pattern", "commit_page", "--format", "json", "--limit", "5"],
        "cbm_trace_enqueue": WSL + ["cli", "--json", "trace_path", "--project", "r06_observer_recheck_src", "--function-name", "r06_observer_recheck_src.ai_intel.ingestion.source_jobs.enqueue_source_page", "--direction", "both", "--depth", "2", "--limit", "80", "--max-output-tokens", "6000", "--include-evidence", "true", "--format", "json"],
        "cbm_trace_commit": WSL + ["cli", "--json", "trace_path", "--project", "r06_observer_recheck_src", "--function-name", "r06_observer_recheck_src.ai_intel.ingestion.cursor_repository.SourceCursorRepository.commit_page", "--direction", "both", "--depth", "1", "--limit", "80", "--max-output-tokens", "6000", "--include-evidence", "true", "--format", "json"],
        "owned_venv_sync": ["C:/Users/yinha/.local/bin/uv.exe", "sync", "--frozen", "--offline", "--no-config", "--no-python-downloads", "--no-install-project", "--project", str(RUN / "runtime_env"), "--python", PYTHON],
    }
    for previous in ("ruff", "format", "mypy", "unit32", "absent_gate", "independent21", "boundaries_sources_retry2"):
        commands["owned_" + previous] = [owned_python, *commands[previous][1:]]
    for previous in ("independent21", "boundaries_sources_retry2"):
        commands["owned_" + previous].append("owned_environment")
    argv = commands[name]
    started = now()
    timer = time.monotonic()
    log = RUN / f"{name}.log"
    with log.open("xb") as stream:
        result = subprocess.run(argv, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, check=False)
    receipt = {"name": name, "command": argv, "cwd": str(ROOT), "reviewed_code_sha": CODE, "material_sha": MATERIAL, "head_sha": HEAD, "started_at": started, "ended_at": now(), "elapsed_seconds": round(time.monotonic() - timer, 6), "exit_code": result.returncode, "expected_exit_code": 1 if name in ("absent_gate", "owned_absent_gate") else 0, "log": log.name, "log_sha256": hashlib.sha256(log.read_bytes()).hexdigest()}
    save(f"{name}_receipt.json", receipt)
    print(json.dumps(receipt, ensure_ascii=False))


if __name__ == "__main__":
    if sys.argv[1] == "manifest":
        manifest()
    elif sys.argv[1] == "copy_source":
        copy_source()
    else:
        command(sys.argv[1])
