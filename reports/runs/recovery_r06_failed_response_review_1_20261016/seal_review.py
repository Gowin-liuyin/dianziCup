"""Seal real review results and verify staged raw bytes without modifying product files."""

import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
REPORT = ROOT / "reports/reviews/recovery/G-C-R06-failed-response-review-1.md"
CODE_SHA = "9eb01d7ba843116122a9a2462f3b74a2626cc48c"


def now():
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()


source_files = [
    "backend/migrations/versions/0016_source_response_receipts.py",
    "backend/src/ai_intel/ingestion/source_failure_models.py",
    "backend/src/ai_intel/ingestion/source_failure_receipts.py",
    "backend/src/ai_intel/ingestion/source_jobs.py",
    "backend/src/ai_intel/knowledge/revisions.py",
    "backend/tests/integration/test_r06_failed_response_legacy_pg.py",
    "backend/tests/integration/test_r06_failed_response_persistence_pg.py",
    "backend/tests/unit/test_r04_source_rate_limits.py",
    "backend/tests/unit/test_r06_failed_response_boundary.py",
    "docs/decisions/CR-R06_failed_response_receipts.md",
]
identities = {}
for path in source_files:
    blob = subprocess.check_output(["git", "show", CODE_SHA + ":" + path], cwd=ROOT)
    working = (ROOT / path).read_bytes()
    identities[path] = {"blob_sha256": hashlib.sha256(blob).hexdigest(), "working_sha256": hashlib.sha256(working).hexdigest(), "normalized_bytes_match": working.replace(b"\r\n", b"\n") == blob.replace(b"\r\n", b"\n")}
assert all(row["normalized_bytes_match"] for row in identities.values())
(RUN / "frozen_source_identity.json").write_text(json.dumps({"checked_at": now(), "code_sha": CODE_SHA, "sources": identities}, indent=2), encoding="utf-8")

counts = {}
for path in sorted(RUN.glob("*.xml")):
    suites = ET.parse(path).getroot()
    counts[path.stem] = {field: sum(int(suite.attrib.get(field, 0)) for suite in suites.iter("testsuite")) for field in ("tests", "failures", "errors", "skipped")}
(RUN / "test_counts.json").write_text(json.dumps(counts, indent=2), encoding="utf-8")

captured = subprocess.check_output(["wsl", "-d", "Ubuntu-22.04", "-u", "root", "--", "cat", "/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json"], text=True, timeout=15)
from sqlalchemy.engine import make_url
private = json.loads(captured)
url = make_url(private["TEST_DATABASE_URL"])
secrets = [private["TEST_DATABASE_URL"], url.password]
files = sorted(path for path in RUN.rglob("*") if path.is_file() and "__pycache__" not in path.parts) + [REPORT]
matches = []
for path in files:
    payload = path.read_bytes()
    if any(value and value.encode() in payload for value in secrets):
        matches.append(str(path.relative_to(ROOT)))
assert matches == []
(RUN / "secret_scan.json").write_text(json.dumps({"checked_at": now(), "checked_files": len(files), "credential_sources": ["authorized private WSL test connection captured in memory"], "provider_secrets_read": 0, "matches": matches}, indent=2), encoding="utf-8")

files = sorted(path for path in RUN.rglob("*") if path.is_file() and "__pycache__" not in path.parts and path.name not in {"artifact_manifest.json", "staged_bytes_audit.json"}) + [REPORT]
manifest = {"frozen_at": now(), "code_sha": CODE_SHA, "verdict": "needs_changes", "artifacts": {str(path.relative_to(ROOT)).replace("\\", "/"): {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "size_bytes": path.stat().st_size} for path in files}}
(RUN / "artifact_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
subprocess.run(["git", "-c", "core.autocrlf=false", "add", "--", str(RUN), str(REPORT)], cwd=ROOT, check=True, capture_output=True)
rows = []
for path in files + [RUN / "artifact_manifest.json"]:
    relative = str(path.relative_to(ROOT)).replace("\\", "/")
    blob = subprocess.check_output(["git", "show", ":" + relative], cwd=ROOT)
    original = path.read_bytes()
    rows.append({"path": relative, "working_sha256": hashlib.sha256(original).hexdigest(), "staged_blob_sha256": hashlib.sha256(blob).hexdigest(), "matches": original == blob})
assert all(row["matches"] for row in rows)
(RUN / "staged_bytes_audit.json").write_text(json.dumps({"checked_at": now(), "checked_files": len(rows), "all_match": True, "artifacts": rows, "exclusions": ["staged_bytes_audit.json describes staged artifacts and cannot self-hash"]}, indent=2), encoding="utf-8")
subprocess.run(["git", "-c", "core.autocrlf=false", "add", "--", str(RUN / "staged_bytes_audit.json")], cwd=ROOT, check=True, capture_output=True)
print(json.dumps({"frozen_at": manifest["frozen_at"], "counts": counts, "staged_bytes_files": len(rows), "secret_matches": len(matches)}))
