"""Check frozen material Git blobs, all own resources and evidence without leaking text."""

import ast
import ctypes
import hashlib
import io
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from sqlalchemy import create_engine, text

from control import MATERIAL, ROOT, RUN, SHA, now, private_url, write


def blob(commit, path):
    return subprocess.check_output(["git", "show", commit + ":" + path], cwd=ROOT)


def digest(value):
    return hashlib.sha256(value).hexdigest()


def definitions(content):
    content = content.decode("utf-8")
    lines = content.splitlines(keepends=True)
    return {node.name: "".join(lines[node.lineno - 1:node.end_lineno]).encode("utf-8") for node in ast.parse(content).body if isinstance(node, ast.FunctionDef)}


manifest_path = "reports/runs/recovery_r06_bulk_source_evidence_20261016/artifact_manifest.json"
manifest_git_bytes = blob(MATERIAL, manifest_path)
manifest_bytes = (Path("D:/wt/r06-bulk-evidence") / manifest_path).read_bytes()
assert digest(manifest_bytes) == "2c0c3fffc1dc078ead919500842859fa63286de86f09477831a6285241fe1aca"
assert manifest_git_bytes == manifest_bytes.replace(b"\r\n", b"\n")
manifest = json.loads(manifest_bytes)
assert manifest["code_commit"] == SHA
assert subprocess.check_output(["git", "rev-parse", SHA + "^{tree}"], cwd=ROOT, text=True).strip() == manifest["code_tree"] == "25bcfe534c447b5b83d4bceed9b1393cfb266109"
archive_entry = manifest["frozen_byte_archive"]
archive_bytes = blob(MATERIAL, archive_entry["path"])
assert len(archive_bytes) == archive_entry["bytes"] and digest(archive_bytes) == archive_entry["sha256"]
archive = zipfile.ZipFile(io.BytesIO(archive_bytes))
checked_material = []
for entry in manifest["code_files"] + manifest["artifacts"]:
    data = archive.read(entry["path"])
    git_data = blob(MATERIAL, entry["path"])
    assert len(data) == entry["bytes"] and digest(data) == entry["sha256"]
    assert git_data == data or git_data == data.replace(b"\r\n", b"\n")
    checked_material.append({"path": entry["path"], "original_bytes": len(data), "original_sha256": digest(data), "git_blob_bytes": len(git_data), "git_blob_sha256": digest(git_data), "git_line_ending_normalization_only": data != git_data})
checked_material.append(archive_entry)
base = definitions(blob("8a1b04d48346d8550f0326a77f003246a0ebbab5", "backend/src/ai_intel/knowledge/revisions.py"))
candidate = definitions(blob(SHA, "backend/src/ai_intel/knowledge/revisions.py"))
legacy = {}
for name in ("add_text_block", "attach_evidence_span", "save_document_revision", "register_response_content"):
    assert base[name] == candidate[name]
    legacy[name] = digest(candidate[name])
old_r04 = blob("8a1b04d48346d8550f0326a77f003246a0ebbab5", "backend/tests/integration/test_r04_source_documents.py")
new_r04 = blob(SHA, "backend/tests/integration/test_r04_source_documents.py")
assert old_r04 == new_r04
actual_worktree = []
for entry in manifest["code_files"]:
    working_bytes = (ROOT / entry["path"]).read_bytes()
    assert working_bytes.replace(b"\r\n", b"\n") == blob(SHA, entry["path"])
    actual_worktree.append({"path": entry["path"], "physical_bytes": len(working_bytes), "physical_sha256": digest(working_bytes), "git_blob_sha256": digest(blob(SHA, entry["path"])), "author_original_sha256": entry["sha256"], "checkout_crlf_only": working_bytes != blob(SHA, entry["path"])})
raw = Path(manifest["raw_external_only"]["path"]).read_bytes()
assert len(raw) == 616865 and digest(raw) == "25e00623a07dcafe8d8d6b3535e400e078ef758e965742a37fe76d5186bb69f7"
diagnostic_root = Path("D:/wt/r06-release-pg-diagnosis")
diagnostic_manifest_bytes = (diagnostic_root / "reports/runs/recovery_r06_large_release_pg_diagnosis_20261016/artifact_manifest.json").read_bytes()
assert digest(diagnostic_manifest_bytes) == "d223c872a6844f6419521e7164da2b6fdc9ae0427a5b4085dd2f2bf58048d1cc"
diagnostic_manifest = json.loads(diagnostic_manifest_bytes)
assert len(diagnostic_manifest["files"]) == 81
for path, entry in diagnostic_manifest["files"].items():
    content = (diagnostic_root / path).read_bytes()
    assert len(content) == entry["bytes"] and digest(content) == entry["sha256"]
url = private_url()
resource_states = []
seen_databases = set()
for identity_path in sorted(RUN.glob("*_identity.json")):
    identity = json.loads(identity_path.read_text(encoding="utf-8"))
    if "database" not in identity:
        continue
    database = identity["database"]
    assert database.startswith("test_dianzi_r06_catalog_bulk_review1_")
    if database in seen_databases:
        continue
    seen_databases.add(database)
    engine = create_engine(url.set(database=database), hide_parameters=True, connect_args={"connect_timeout": 3, "options": "-c statement_timeout=3000 -c default_transaction_read_only=on"})
    with engine.connect() as connection:
        connection.execute(text("SET TRANSACTION READ ONLY"))
        assert connection.scalar(text("SELECT current_database()")) == database
        sessions = connection.scalar(text("SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid()"))
        schemas = connection.execute(text("SELECT nspname FROM pg_namespace WHERE nspname LIKE 'test_r06_%'")).scalars().all()
        assert sessions == 0 and schemas == []
        resource_states.append({"identity": identity_path.name, "database": database, "transaction_read_only": connection.scalar(text("SHOW transaction_read_only")), "other_sessions": sessions, "remaining_test_schemas": schemas})
    engine.dispose()
kernel = ctypes.WinDLL("kernel32", use_last_error=True)
kernel.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
kernel.OpenProcess.restype = ctypes.c_void_p
kernel.CloseHandle.argtypes = [ctypes.c_void_p]
kernel.GetProcessTimes.argtypes = [ctypes.c_void_p] + [ctypes.POINTER(ctypes.c_ulonglong)] * 4
kernel.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
processes = []
for identity_path in RUN.glob("replay_*_process_identity.json"):
    identity = json.loads(identity_path.read_text(encoding="utf-8"))
    handle = kernel.OpenProcess(0x1000, False, identity["pid"])
    active_same_process = False
    if handle:
        created, exited, cpu_kernel, cpu_user = (ctypes.c_ulonglong() for _ in range(4))
        status = ctypes.c_ulong()
        if kernel.GetProcessTimes(handle, ctypes.byref(created), ctypes.byref(exited), ctypes.byref(cpu_kernel), ctypes.byref(cpu_user)) and kernel.GetExitCodeProcess(handle, ctypes.byref(status)):
            creation = (created.value - 116444736000000000) / 10000000
            active_same_process = abs(creation - identity["creation_time_epoch"]) < 0.01 and status.value == 259
        kernel.CloseHandle(handle)
    assert not active_same_process
    processes.append({"pid": identity["pid"], "creation_time_epoch": identity["creation_time_epoch"], "same_process_active": active_same_process})
tests = {}
for path in RUN.glob("*.xml"):
    suites = ET.parse(path).getroot()
    cases = suites.findall(".//testcase")
    tests[path.name] = {"tests": len(cases), "failures": sum(case.find("failure") is not None for case in cases), "errors": sum(case.find("error") is not None for case in cases), "skipped": sum(case.find("skipped") is not None for case in cases)}
secrets = [url.render_as_string(hide_password=False).encode(), url.password.encode()]
for path in RUN.rglob("*"):
    if path.is_file() and path.name != "artifact_manifest.json":
        content = path.read_bytes()
        assert raw not in content
        assert all(secret not in content for secret in secrets)
replays = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(RUN.glob("replay_*_result.json"))]
assert len(replays) == len(list(RUN.glob("replay_*_execution_start.json"))) == 2
for result in replays:
    assert result["invalid_evidence"] == 0 and result["cas_objects_verified"] == 21
    assert result["sampler_stopped"] and result["process_identity"]["cpu_rate"] == 2000
    assert result["process_identity"]["memory_per_process"] == 536870912 and result["process_identity"]["memory_total"] == 2147483648
controller_seconds = [json.loads(path.read_text(encoding="utf-8"))["total_wall_seconds"] for path in RUN.glob("replay_*_controller.json")]
assert all(seconds <= 120 for seconds in controller_seconds) and sum(controller_seconds) <= 240
write(sys.argv[1] if len(sys.argv) > 1 else "audit_receipt.json", {"observed_at": now(), "reviewed_sha": SHA, "tree": manifest["code_tree"], "author_material_commit": MATERIAL, "author_manifest_sha256": digest(manifest_bytes), "author_manifest_git_blob_sha256": digest(manifest_git_bytes), "author_manifest_git_blob_oid": subprocess.check_output(["git", "rev-parse", MATERIAL + ":" + manifest_path], cwd=ROOT, text=True).strip(), "material_entries_verified": len(checked_material), "material_entries": checked_material, "diagnostic_manifest_sha256": digest(diagnostic_manifest_bytes), "diagnostic_entries_verified": len(diagnostic_manifest["files"]), "unchanged_legacy_definition_sha256": legacy, "unchanged_r04_git_blob_sha256": digest(new_r04), "worktree_bytes": actual_worktree, "raw_sha256": digest(raw), "raw_bytes": len(raw), "resources": resource_states, "actual_raw_handler_count": len(replays), "replay_controller_seconds": controller_seconds, "replay_total_controller_wall_seconds": sum(controller_seconds), "replay_processes": processes, "tests": tests, "raw_body_scan_matches": 0, "credential_scan_matches": 0, "scan_scope": "exact original raw bytes, captured test base URL and credential in own run files; no secret vault/provider scan"})
print(json.dumps({"material_entries_verified": len(checked_material), "own_database_snapshots": len(resource_states), "actual_raw_handlers": len(replays), "replay_total_wall_seconds": sum(controller_seconds), "tests": tests}, ensure_ascii=False))
