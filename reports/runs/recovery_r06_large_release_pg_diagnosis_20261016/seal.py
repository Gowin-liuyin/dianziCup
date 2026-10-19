"""Seal original input metadata and this report without copying response bodies."""

import ast
import hashlib
import json
import subprocess
from pathlib import Path

from control import ROOT, RUN, SHA, now, write

original = Path("D:/dianzi/reports/runs/recovery_r06_live_segment_8a_20261016")
names = ["release_export_receipt.json", "diagnosis_receipt.json", "runtime_start.json", "runtime_end.json",
         "terminal_seal_receipt.json", "supervise.py", "runtime_limits.py", "worker.log",
         "observer_terminal_archive/collection_end.json", "observer_terminal_archive/collection_latest.json",
         "observer_terminal_archive/collection_observations.jsonl", "observer_terminal_archive/collector_stop.request"]
original_files = {}
for name in names:
    path = original / name
    payload = path.read_bytes()
    original_files[name] = {"absolute_path": str(path), "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}
raw = Path("D:/dianzi-local-evidence/recovery_r06_live_segment_8a_20261016/release_raw.bin")
raw_bytes = raw.read_bytes()
assert len(raw_bytes) == 616865
assert hashlib.sha256(raw_bytes).hexdigest() == "25e00623a07dcafe8d8d6b3535e400e078ef758e965742a37fe76d5186bb69f7"
write("original_evidence_manifest.json", {"sealed_at": now(), "original_files": original_files,
      "raw": {"absolute_path": str(raw), "bytes": len(raw_bytes), "sha256": hashlib.sha256(raw_bytes).hexdigest(), "outside_repository": True},
      "original_files_modified_by_diagnosis": False})
for path in RUN.glob("*.py"):
    ast.parse(path.read_text(encoding="utf-8"))
report = ROOT / "reports/tasks/R06-large-release-persistence-diagnosis.md"
assert report.exists()
assert not subprocess.check_output(["git", "diff", "HEAD", "--", "backend/src", "backend/tests", "config", "contracts", "progress", "frontend"], cwd=ROOT)
paths = [path for path in RUN.rglob("*") if path.is_file() and path.name != "artifact_manifest.json"] + [report]
records = {}
for path in paths:
    payload = path.read_bytes()
    assert raw_bytes not in payload
    records[str(path.relative_to(ROOT))] = {"bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}
write("artifact_manifest.json", {"sealed_at": now(), "reviewed_sha": SHA, "reviewed_tree": "c614a6cb784c8fab422a14479d14ea4b6303493c",
      "cbm_scope": "own backend/src only; excludes ai_intel/assets; independent cache; no report/test/raw/holdout index",
      "files": records, "manifest_excludes_itself": True, "raw_bytes_in_repository": False, "product_sources_tests_config_contracts_state_unchanged": True})
print(json.dumps({"seal": "passed", "original_files": len(original_files), "artifact_files": len(records), "python_syntax": "passed", "raw_hash_verified": True}))
