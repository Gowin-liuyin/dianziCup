"""Verify offline artifacts and stopped owned children without running a third replay."""

import ctypes
import hashlib
import json
import re
import subprocess
from ctypes import wintypes
from pathlib import Path

from sqlalchemy import create_engine, text

from control import ROOT, RUN, SHA, load_url, now, write

raw = Path("D:/dianzi-local-evidence/recovery_r06_live_segment_8a_20261016/release_raw.bin").read_bytes()
assert len(raw) == 616865
assert hashlib.sha256(raw).hexdigest() == "25e00623a07dcafe8d8d6b3535e400e078ef758e965742a37fe76d5186bb69f7"
raw_records = json.loads(raw)
assert isinstance(raw_records, list) and len(raw_records) == 20
checks = []
for number in ("3", "4"):
    result = json.loads((RUN / ("replay_" + number + "_result.json")).read_text())
    assert result["outcome"] == "succeeded"
    assert result["counts"]["documents"] == len(raw_records) == result["counts"]["revisions"]
    assert result["counts"]["text_blocks"] == result["counts"]["evidence"] == 11827
    assert result["invalid_evidence"] == 0 and result["cas_objects_verified"] == 21
    assert result["counts"]["page_receipts"] == result["counts"]["response_receipts"] == 1
    assert result["cursors"][0]["last_successful_page"] == 1 and result["cursors"][0]["lease_owner"] is None
    assert result["network"] == {"fixture_fetch_calls": 1, "http_transport_calls": 0, "nonlocal_socket_attempts": 0}
    assert result["sampler_stopped"]
    journal = [json.loads(line) for line in (RUN / ("replay_" + number + "_samples.jsonl")).read_text().splitlines()]
    checks.append({"replay": number, "records": len(journal), "blocking_samples": sum(any(row["blocking_pids"] for row in sample["states"]) for sample in journal),
                   "ungranted_lock_samples": sum(any(not row["granted"] for row in sample["locks"]) for sample in journal),
                   "lock_wait_samples": sum(any(row["wait_event_type"] == "Lock" for row in sample["states"]) for sample in journal),
                   "at_or_after_35_seconds": next({key: sample[key] for key in ("observed_at", "elapsed_seconds", "progress", "sql_count")} for sample in journal if sample["elapsed_seconds"] >= 35)})

kernel = ctypes.WinDLL("kernel32", use_last_error=True)
kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel.OpenProcess.restype = wintypes.HANDLE
kernel.CloseHandle.argtypes = [wintypes.HANDLE]
kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
processes = []
for path in sorted(RUN.glob("replay_*_command.json")):
    record = json.loads(path.read_text())
    handle = kernel.OpenProcess(0x1000, False, record["pid"])
    active = False
    if handle:
        exit_code = wintypes.DWORD()
        assert kernel.GetExitCodeProcess(handle, ctypes.byref(exit_code))
        active = exit_code.value == 259
        kernel.CloseHandle(handle)
    assert not active
    processes.append({"pid": record["pid"], "process_active_at_audit": active, "popen_wait_confirmed": record["terminated_and_waited"], "command_exit_code": record["exit_code"]})

database_sessions = []
url = load_url()
for path in sorted(RUN.glob("replay_*_identity.json")):
    if re.fullmatch(r"replay_[0-9]+_identity.json", path.name) is None:
        continue
    database = json.loads(path.read_text())["database"]
    engine = create_engine(url.set(database=database), hide_parameters=True, connect_args={"connect_timeout": 3, "options": "-c statement_timeout=3000 -c default_transaction_read_only=on"})
    with engine.connect() as connection:
        connection.execute(text("SET TRANSACTION READ ONLY"))
        sessions = [dict(row) for row in connection.execute(text("select pid,state,wait_event_type,wait_event from pg_stat_activity where datname=current_database() and pid<>pg_backend_pid()")).mappings()]
        assert not sessions
        database_sessions.append({"database": database, "active_sessions_excluding_readonly_auditor": sessions})
    engine.dispose()

files = [path for path in RUN.rglob("*") if path.is_file()]
leaks = []
for path in files:
    body = path.read_bytes()
    if raw in body or re.search(rb"postgresql(?:\+psycopg)?://", body):
        leaks.append(str(path.relative_to(RUN)))
assert not leaks
assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip() == SHA
assert not subprocess.check_output(["git", "diff", "HEAD", "--", "backend/src", "backend/tests", "config", "contracts", "progress", "frontend"], cwd=ROOT)
write("audit_receipt.json", {"audited_at": now(), "reviewed_sha": SHA, "reviewed_tree": subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], cwd=ROOT, text=True).strip(),
      "two_actual_replays": checks, "owned_child_processes": processes, "isolated_database_sessions": database_sessions,
      "raw_file_hash_and_size_verified": True, "body_or_dsn_in_run_files": leaks, "files_scanned": len(files),
      "scan_scope": "exact whole-body bytes and credential-bearing PostgreSQL URL; no DPAPI/provider secret was read", "unchanged_product_test_contract_config_state_frontend": True,
      "api_worker_beat_minio_started_by_diagnosis": False, "http_requests_from_replay": 0, "external_api_or_asset_requests": 0,
      "run_total_recorded_wall_seconds_including_bootstrap_and_prelaunch_failure": sum(json.loads(path.read_text())["wall_seconds"] for path in RUN.glob("replay_*_command.json")) + json.loads((RUN / "replay_4_prelaunch_failure.json").read_text())["wall_seconds_from_tool"]})
print(json.dumps({"audit": "passed", "actual_replays": 2, "owned_children_inactive": len(processes), "database_sessions": 0, "files_scanned": len(files), "body_or_dsn_leaks": 0}))
