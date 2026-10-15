"""Commit only the frozen manifest's owned evidence paths, preserving raw bytes."""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
manifest_path = RUN / "artifact_manifest.json"
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip() == manifest["code_sha"]
existing = subprocess.check_output(["git", "diff", "--cached", "--name-only"], cwd=ROOT, text=True).splitlines()
assert all(path == "reports/tasks/R12-production-hybrid-migration.md" or path.startswith("reports/runs/recovery_r12_runtime_integration_20261016/") for path in existing)
paths = [item["path"] for item in manifest["members"]]
for item in manifest["members"]:
    path = ROOT / item["path"]
    assert path.resolve().is_relative_to(ROOT.resolve())
    assert item["path"] == "reports/tasks/R12-production-hybrid-migration.md" or item["path"].startswith("reports/runs/recovery_r12_runtime_integration_20261016/")
    assert hashlib.sha256(path.read_bytes()).hexdigest() == item["sha256"]
paths.append(manifest_path.relative_to(ROOT).as_posix())
subprocess.run(["git", "add", "--", *paths], cwd=ROOT, check=True, capture_output=True)
checked = subprocess.run(["git", "diff", "--cached", "--check"], cwd=ROOT, capture_output=True)
(RUN / "material_check.log").write_bytes(checked.stdout + checked.stderr)
assert checked.returncode == 0, "raw whitespace retained; inspect exact exception before commit"
committed = subprocess.run(["git", "commit", "-m", "G-D archive forward hybrid schema evidence awaiting independent review"], cwd=ROOT, capture_output=True, check=True)
(RUN / "material_commit.log").write_bytes(committed.stdout + committed.stderr)
head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
for item in manifest["members"]:
    blob = subprocess.check_output(["git", "show", head + ":" + item["path"]], cwd=ROOT)
    assert hashlib.sha256(blob).hexdigest() == item["sha256"], "raw/Git evidence mismatch"
receipt = {"observed_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(), "code_sha": manifest["code_sha"], "material_sha": head, "members": len(manifest["members"]), "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(), "raw_blob_differences": 0, "stage_accepted": False, "push": "not_run"}
(RUN / "material_commit_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps(receipt))
