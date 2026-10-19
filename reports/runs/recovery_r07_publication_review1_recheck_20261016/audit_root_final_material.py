"""Check final root material in a separate detached checkout without using mutable author files."""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RAW = Path(__file__).resolve().parent
MATERIAL = Path("D:/wt/r07-pub-matcheck1")
SHA = "9e722c944cf83086ffd30ad24a708172c13da189"
RELATIVE = "reports/runs/recovery_r07_publication_combined_fix_20261016/artifact_manifest.json"
manifest = MATERIAL / RELATIVE
data = json.loads(manifest.read_text(encoding="utf-8"))
failures = []
for row in data["artifacts"]:
    path = MATERIAL / row["path"]
    blob = subprocess.run(["git", "show", SHA + ":" + row["path"]], cwd=MATERIAL, capture_output=True, check=True).stdout
    if hashlib.sha256(path.read_bytes()).hexdigest() != row["sha256"] or hashlib.sha256(blob).hexdigest() != row["sha256"] or len(blob) != row["bytes"]:
        failures.append(row["path"])
blob_manifest = subprocess.run(["git", "show", SHA + ":" + RELATIVE], cwd=MATERIAL, capture_output=True, check=True).stdout
code_diff = subprocess.run(["git", "diff", "--name-status", "dc04d193185324f6913cde8efc40f4b238047dd8.." + SHA, "--", "backend/src", "backend/tests", "backend/uv.lock", "backend/pyproject.toml"], cwd=MATERIAL, capture_output=True, text=True, check=True).stdout
document_diff = subprocess.run(["git", "diff", "--name-status", "dc04d193185324f6913cde8efc40f4b238047dd8.." + SHA, "--", "docs", "reports/tasks", ".gitattributes"], cwd=MATERIAL, capture_output=True, text=True, check=True).stdout
report = MATERIAL / "reports/tasks/R07-publication-combined-fix.md"
record = {"checked_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(), "material_sha": SHA,
    "code_sha": data["code_sha"], "code_tree": data["code_tree"], "sealed_at": data["sealed_at"],
    "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(), "manifest_working_bytes_equal_git_blob": manifest.read_bytes() == blob_manifest,
    "artifact_count": len(data["artifacts"]), "artifact_runtime_and_git_blob_mismatches": failures,
    "report_sha256": hashlib.sha256(report.read_bytes()).hexdigest(), "source_test_lock_diff": code_diff,
    "document_attribute_diff": document_diff,
    "old_v1_manifest_sha256": hashlib.sha256((manifest.parent / "artifact_manifest_v1_uncommitted.json").read_bytes()).hexdigest(),
    "old_v1_report_sha256": hashlib.sha256((manifest.parent / "report_v1_uncommitted.md").read_bytes()).hexdigest()}
(RAW / "root_final_material_audit.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
assert not failures and not code_diff
assert record["manifest_sha256"] == "adf134ab772ab8867322633bce990cfe47c008e5737f2ca45a851aed09cbb91e"
assert record["report_sha256"] == "f3a90b67536a27f5696741a80db70dd6900ed8c7fcb21649cb0b0a3f052f541a"
print(json.dumps(record, ensure_ascii=False))
