"""Preserve the listed raw evidence; explicitly exclude generated caches from Git proof."""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
PREFIX = RUN.relative_to(ROOT).as_posix() + "/"
CODE_SHA = "ba69d6cbc2bc4828a56bdc8c7d2f2c95c4dda5ce"
ORIGINAL_MANIFEST_SHA = "2dbdad200695ea322ab104548f068c2fdd86f42d2abc80fb76139d6c3ab1826a"
started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
raw_path = RUN / "raw_manifest.json"
assert hashlib.sha256(raw_path.read_bytes()).hexdigest() == ORIGINAL_MANIFEST_SHA
manifest = json.loads(raw_path.read_bytes())
cache_rows = [row for row in manifest["materials"] if "/__pycache__/" in row["path"] and row["path"].endswith(".pyc")]
assert len(cache_rows) == 5
for row in cache_rows:
    assert subprocess.run(["git", "ls-files", "--error-unmatch", "--", row["path"]], cwd=ROOT, capture_output=True).returncode != 0
rows = [row for row in manifest["materials"] if row not in cache_rows]
assert len(rows) == 48
for row in rows:
    assert hashlib.sha256((ROOT / row["path"]).read_bytes()).hexdigest() == row["raw_sha256"], row["path"]
subprocess.run(["git", "add", PREFIX + ".gitattributes"], cwd=ROOT, check=True)
owned_rows = [row for row in rows if row["path"].startswith(PREFIX)]
subprocess.run(["git", "add", "--renormalize", "--", *(row["path"] for row in owned_rows)], cwd=ROOT, check=True)
results = []
for row in rows:
    indexed = subprocess.check_output(["git", "show", ":" + row["path"]], cwd=ROOT)
    digest = hashlib.sha256(indexed).hexdigest()
    assert digest == row["raw_sha256"], row["path"]
    results.append({"path": row["path"], "indexed_blob_sha256": digest, "raw_sha256": row["raw_sha256"], "match": True})
source_results = []
for row in manifest["changed_source"]:
    indexed = subprocess.check_output(["git", "show", ":" + row["path"]], cwd=ROOT)
    frozen = subprocess.check_output(["git", "show", CODE_SHA + ":" + row["path"]], cwd=ROOT)
    digest = hashlib.sha256(indexed).hexdigest()
    assert indexed == frozen and digest == row["lf_sha256"], row["path"]
    source_results.append({"path": row["path"], "indexed_blob_sha256": digest, "frozen_code_sha256": hashlib.sha256(frozen).hexdigest(), "original_lf_sha256": row["lf_sha256"], "match": True})
new_names = [".gitattributes", "bytes_fix_report.md", "restage_raw_materials.py", "scan_actual_values_bytes_fix.py", "actual_value_scan_bytes_fix.json"]
subprocess.run(["git", "add", "--", *(PREFIX + name for name in new_names)], cwd=ROOT, check=True)
checks = []
commands = (
    ("source_diff", ["git", "diff", "--check", CODE_SHA, "--", "backend/src", "backend/tests"]),
    ("source_unchanged", ["git", "diff", "--quiet", CODE_SHA, "--", "backend/src", "backend/tests"]),
    ("material_staged_diff", ["git", "diff", "--cached", "--check"]),
)
for name, command in commands:
    check = subprocess.run(command, cwd=ROOT, capture_output=True)
    log_name = name + "_bytes_fix.log"
    (RUN / log_name).write_bytes(check.stdout + check.stderr)
    new_names.append(log_name)
    checks.append({"name": name, "command": command, "exit_code": check.returncode})
subprocess.run(["git", "add", "--", *(PREFIX + name for name in new_names)], cwd=ROOT, check=True)
additional_results = []
for name in [*new_names, "raw_manifest.json", "material_fingerprint.json"]:
    path = PREFIX + name
    raw = (ROOT / path).read_bytes()
    indexed = subprocess.check_output(["git", "show", ":" + path], cwd=ROOT)
    assert indexed == raw, path
    additional_results.append({"path": path, "raw_sha256": hashlib.sha256(raw).hexdigest(), "indexed_blob_sha256": hashlib.sha256(indexed).hexdigest(), "match": True})
receipt = {
    "started_at": started,
    "completed_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
    "code_sha": CODE_SHA,
    "prior_material_sha": "a92cc7c64592a06a00317e0ae2887124d3c51141",
    "raw_manifest_sha256": ORIGINAL_MANIFEST_SHA,
    "raw_manifest_unchanged": hashlib.sha256(raw_path.read_bytes()).hexdigest() == ORIGINAL_MANIFEST_SHA,
    "explicit_owned_rows_restaged": len(owned_rows),
    "original_material_rows_git_verified": results,
    "source_rows_frozen_code_verified": source_results,
    "additional_material_rows_git_verified": additional_results,
    "excluded_generated_cache_rows": [{**row, "policy": "excluded", "verification": "not_Git_verified", "current_content_read": False} for row in cache_rows],
    "checks": checks,
    "historical_bootstrap_started_at": None,
    "historical_bootstrap_completed_at": None,
    "original_red_counts": "preserved",
    "task_state": "awaiting_review",
    "self_hash": "external receipt only; this manifest does not include itself",
}
receipt_bytes = json.dumps(receipt, indent=2).encode()
(RUN / "bytes_fix_manifest.json").write_bytes(receipt_bytes)
subprocess.run(["git", "add", "--", PREFIX + "bytes_fix_manifest.json"], cwd=ROOT, check=True)
assert subprocess.check_output(["git", "show", ":" + PREFIX + "bytes_fix_manifest.json"], cwd=ROOT) == receipt_bytes
print(json.dumps({"original_rows_git_verified": len(results), "source_rows_frozen_code_verified": len(source_results), "generated_cache_rows_excluded": len(cache_rows), "additional_rows_git_verified": len(additional_results), "bytes_fix_manifest_sha256": hashlib.sha256(receipt_bytes).hexdigest(), "checks": checks}))
raise SystemExit(next((check["exit_code"] for check in checks if check["exit_code"]), 0))
