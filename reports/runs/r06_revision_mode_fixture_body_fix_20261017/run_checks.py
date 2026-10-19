"""Bounded report-only checks; no credentials, services, or database fixtures are loaded."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shlex
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
PYTHON = Path("D:/dianzi/backend/.venv/Scripts/python.exe")
METADATA = Path("D:/wt/r20-backup-review1/reports/runs/recovery_r20_backup_restore_review1_20261016/process_metadata.py")
spec = importlib.util.spec_from_file_location("owned_metadata", METADATA)
identity_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(identity_module)
CONTROL, ANCESTRY = identity_module.control_root(identity_module.current_identity())
CACHE = "/tmp/r06-revision-mode-fixture-body-fix-cbm-20261017"
PROJECT = "r06_revision_mode_fixture_body_fix_48f96b5"
BINARY = "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp"
LINUX_RUN = "/mnt/d/wt/r06-revision-mode-fixture-body-fix/reports/runs/r06_revision_mode_fixture_body_fix_20261017"


def now():
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def linux_owned():
    proc = Path(r"\\wsl.localhost\Ubuntu-22.04\proc")
    marker = RUN / "tool_active_host.stat"
    if not marker.exists():
        return {}
    marker_row = marker.read_text().strip().split(" ", 1)[1]
    root_pid = int(marker_row.split(" ", 1)[0])
    root_ticks = int(marker_row.rsplit(")", 1)[1].split()[19])
    rows = {}
    for item in proc.iterdir():
        if not item.name.isdigit():
            continue
        try:
            row = (item / "stat").read_text()
            fields = row.rsplit(")", 1)[1].split()
            rows[int(item.name)] = {"pid": int(item.name), "parent_pid": int(fields[1]), "birth_ticks": int(fields[19]), "name": row.split("(", 1)[1].rsplit(")", 1)[0]}
        except (OSError, ValueError, IndexError):
            continue
    if root_pid not in rows or rows[root_pid]["birth_ticks"] != root_ticks:
        return {}
    owned = {root_pid: rows[root_pid]}
    parent = rows[root_pid]["parent_pid"]
    if parent in rows and rows[parent]["name"] == "SessionLeader" and rows[parent]["birth_ticks"] <= root_ticks:
        owned[parent] = rows[parent]
    while True:
        added = {pid: row for pid, row in rows.items() if pid not in owned and row["parent_pid"] in owned and row["birth_ticks"] >= owned[row["parent_pid"]]["birth_ticks"]}
        if not added:
            return owned
        owned.update(added)


def run(name, command, *, cap=10, wsl=False):
    if (RUN / (name + ".receipt.json")).exists():
        raise ValueError("existing run receipts must not be overwritten")
    env = {key: value for key, value in os.environ.items() if not key.startswith("TEST_") and not any(word in key.upper() for word in ("TOKEN", "SECRET", "API_KEY", "DATABASE_URL", "REDIS_URL"))}
    env["PYTHONPATH"] = os.pathsep.join(str(ROOT / name) for name in ("backend", "backend/src", "backend/tests/integration"))
    env["MYPYPATH"] = os.pathsep.join(str(ROOT / name) for name in ("backend", "backend/src"))
    env["PYTHONUTF8"] = "1"
    samples = []
    stop = threading.Event()
    started = now()
    start = time.monotonic()
    errors = []

    def monitor():
        while not stop.is_set():
            try:
                windows = identity_module.descendants(CONTROL)
                linux = linux_owned() if wsl else {}
                count = len(windows) + len(linux)
                samples.append({"elapsed_seconds": round(time.monotonic() - start, 3), "windows": list(windows.values()), "linux": list(linux.values()), "own_full_tree_count": count})
                if count > cap:
                    errors.append("own full tree count exceeded bound")
                    return
            except (OSError, ValueError, IndexError) as error:
                errors.append(type(error).__name__)
                return
            stop.wait(0.05)

    with (RUN / (name + ".stdout.log")).open("wb") as stdout, (RUN / (name + ".stderr.log")).open("wb") as stderr:
        process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=stdout, stderr=stderr)
        monitor_thread = threading.Thread(target=monitor)
        monitor_thread.start()
        try:
            while process.poll() is None:
                if errors or time.monotonic() - start >= 60:
                    process.kill()
                    process.wait(timeout=5)
                    errors.append("controlled subprocess terminated")
                    break
                time.sleep(0.05)
        finally:
            stop.set()
            monitor_thread.join(timeout=2)
    result = {"command": command, "cwd": str(ROOT), "started_at": started, "ended_at": now(), "duration_seconds": round(time.monotonic() - start, 3), "exit_code": process.returncode, "cap": cap, "samples": samples, "maximum_own_full_tree": max((sample["own_full_tree_count"] for sample in samples), default=0), "control_root": CONTROL, "ancestry": ANCESTRY, "errors": errors, "metadata_helper_sha256": hashlib.sha256(METADATA.read_bytes()).hexdigest(), "wsl_owned_after": list(linux_owned().values()) if wsl else [], "credentials_loaded": False}
    (RUN / (name + ".receipt.json")).write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("started_at", "ended_at", "exit_code", "duration_seconds", "maximum_own_full_tree", "errors")}))
    return result


def cbm(name, args):
    shell = "(printf 'shell '; cat /proc/$$/stat) > " + shlex.quote(LINUX_RUN + "/tool_active_host.stat") + "; exec env CBM_CACHE_DIR=" + shlex.quote(CACHE) + " " + shlex.quote(BINARY) + " " + shlex.join(args)
    return run(name, ["wsl.exe", "--exec", "sh", "-c", shell], cap=16, wsl=True)


if __name__ == "__main__":
    pg_test = "backend/tests/integration/test_r06_revision_mode_read_pg.py"
    contract_test = "backend/tests/contract/test_r06_revision_mode_fixture_input_contract.py"
    if sys.argv[1] == "offline":
        run("offline_input_and_read_contracts", [str(PYTHON), "-m", "pytest", contract_test, "backend/tests/unit/test_r06_revision_mode.py", "backend/tests/contract/test_r06_revision_mode_router_contract.py", "--no-cov", "-q", "--junitxml=" + str(RUN / "offline_input_and_read_contracts.xml")])
        run("pg_collect_only", [str(PYTHON), "-m", "pytest", pg_test, "--collect-only", "--no-cov", "-q"])
        run("fixture_mypy", [str(PYTHON), "-m", "mypy", pg_test, contract_test, "--allow-untyped-defs", "--check-untyped-defs", "--follow-imports=silent"])
        run("fixture_ruff", [str(PYTHON), "-m", "ruff", "check", pg_test, contract_test])
        run("fixture_format", [str(PYTHON), "-m", "ruff", "format", "--check", pg_test, contract_test])
    elif sys.argv[1] == "cbm":
        cbm("fixture_cbm_index", ["cli", "--json", "index_repository", "--repo-path", "/mnt/d/wt/r06-revision-mode-fixture-body-fix/backend/tests", "--name", PROJECT, "--mode", "fast"])
        cbm("fixture_cbm_callers", ["cli", "--json", "trace_path", "--project", PROJECT, "--function-name", PROJECT + ".r06_source_worker_fixtures.source_response", "--direction", "both", "--depth", "2", "--format", "json", "--max-output-tokens", "2000"])
    elif sys.argv[1] == "static_fix":
        run("fixture_mypy_correct_import_roots", [str(PYTHON), "-m", "mypy", pg_test, contract_test, "--allow-untyped-defs", "--check-untyped-defs", "--follow-imports=silent"])
        run("fixture_input_strict_mypy", [str(PYTHON), "-m", "mypy", contract_test, "--strict", "--follow-imports=silent"])
    elif sys.argv[1] == "guard":
        run("fixture_oracle_guard", [str(PYTHON), str(RUN / "verify_fixture_fix.py")])
    elif sys.argv[1] == "freeze":
        for label, command in (
            ("source_explicit_add", ["git", "add", "--", pg_test, contract_test]),
            ("source_staged_check", ["git", "diff", "--cached", "--check"]),
            ("source_staged_names", ["git", "diff", "--cached", "--name-only"]),
            ("source_commit", ["git", "commit", "-m", "fix(R06): unpack recorded NVD bytes in mode PG fixture"]),
            ("source_sha", ["git", "rev-parse", "HEAD"]),
        ):
            receipt = run(label, command)
            if receipt["exit_code"] != 0:
                raise SystemExit(receipt["exit_code"])
