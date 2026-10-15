"""Seal source/test artifacts, offline response identities, and actual local check counts."""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree
from zoneinfo import ZoneInfo

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
CODE_SHA = "e900cd6b95dde7c6fe8d11d8c15122eb48a4acdc"

files = [path for path in RUN.iterdir() if path.is_file() and path.name != "fix_manifest.json"]
files.extend([
    ROOT / "reports/tasks/R06-live-compat-fix.md",
    ROOT / "backend/src/ai_intel/ingestion/catalog_pages.py",
    ROOT / "backend/src/ai_intel/ingestion/sources/github_releases.py",
    ROOT / "backend/src/ai_intel/ingestion/sources/avid_records.py",
    ROOT / "backend/tests/unit/test_r06_live_source_compatibility.py",
])
counts = {}
for label in ("tests_red", "tests_green", "unit_regression", "contract_regression", "security_regression"):
    suite = ElementTree.parse(RUN / (label + ".xml")).getroot().find("testsuite")
    counts[label] = {field: int(suite.get(field, "0")) for field in ("tests", "failures", "errors", "skipped")}
changed = subprocess.run(["git", "diff", "--name-only", "1a52e17ffe327fb8a0c1d4f97372948a699910e3", CODE_SHA],
                         cwd=ROOT, capture_output=True, text=True, check=True).stdout.splitlines()
output = {
    "sealed_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
    "base_sha": "1a52e17ffe327fb8a0c1d4f97372948a699910e3", "code_sha": CODE_SHA,
    "worktree": str(ROOT), "task_status": "awaiting_review", "implementation": "complete",
    "independent_review": "not_run", "changed_code_paths": changed, "junit_counts": counts,
    "integration_executed": 0, "integration_collected": 54, "external_requests": 0,
    "database_calls": 0, "model_calls": 0, "measurement_calls": 0,
    "verification": {"unit": "passed", "contract": "passed", "security": "passed",
                     "integration": "not_run", "frontend": "not_run", "e2e": "not_run",
                     "live": "not_run", "manual": "not_run"},
    "artifacts": [{"path": str(path.relative_to(ROOT)), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                   "size_bytes": path.stat().st_size} for path in sorted(files)],
}
(RUN / "fix_manifest.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
print(json.dumps({"code_sha": CODE_SHA, "artifacts": len(files), "junit_counts": counts,
                  "verification": output["verification"]}, indent=2))
