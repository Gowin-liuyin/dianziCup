"""Seal actual outputs and source identities, without retaining private service connections."""

import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlsplit

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
PRODUCT = [
    "backend/src/ai_intel/ingestion/source_jobs.py",
    "backend/src/ai_intel/ingestion/source_failure_receipts.py",
    "backend/tests/unit/test_r06_failed_response_boundary.py",
    "backend/tests/unit/test_r04_source_rate_limits.py",
    "backend/tests/integration/test_r06_failed_response_persistence_pg.py",
    "backend/tests/integration/test_r06_failed_response_legacy_pg.py",
]
DEPENDENCIES = [
    "backend/migrations/versions/0016_source_response_receipts.py",
    "backend/src/ai_intel/ingestion/source_failure_models.py",
    "backend/src/ai_intel/knowledge/revisions.py",
    "docs/decisions/CR-R06_failed_response_receipts.md",
]
configuration = json.loads(subprocess.check_output([
    "wsl", "-d", "Ubuntu-22.04", "-u", "root", "--", "cat",
    "/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json",
], text=True, timeout=10))
connection = configuration["TEST_DATABASE_URL"]
secrets = [connection, unquote(urlsplit(connection).password or "")]
paths = [*RUN.glob("*.log"), *RUN.glob("*.xml"), *RUN.glob("*.json"), *(ROOT / name for name in PRODUCT + DEPENDENCIES)]
paths += [*RUN.glob("*.py"), ROOT / "reports/tasks/R06-failed-response-persistence.md"]
matches = []
for path in paths:
    body = path.read_bytes()
    if any(secret and secret.encode() in body for secret in secrets):
        matches.append(str(path.relative_to(ROOT)))
scan = {"at": datetime.now().astimezone().isoformat(), "checked_files": len(paths), "credential_sources": ["authorized private WSL runtime test connection"], "provider_secrets_read": 0, "matches": matches}
(RUN / "secret_scan.json").write_text(json.dumps(scan, indent=2), encoding="utf-8")
assert not matches
tests = {}
for path in RUN.glob("*.xml"):
    suite = ET.parse(path).getroot().find("testsuite")
    tests[path.stem] = {key: suite.attrib[key] for key in ("tests", "errors", "failures", "skipped", "time")}
    tests[path.stem]["case_files"] = sorted({case.attrib.get("classname", "") for case in suite.findall("testcase")})
(RUN / "test_counts.json").write_text(json.dumps(tests, indent=2), encoding="utf-8")
code_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
source_identity = {}
for name in PRODUCT + DEPENDENCIES:
    blob = subprocess.check_output(["git", "show", f"{code_sha}:{name}"], cwd=ROOT)
    source_identity[name] = {"working_sha256": hashlib.sha256((ROOT / name).read_bytes()).hexdigest(), "git_blob_sha256": hashlib.sha256(blob).hexdigest()}
(RUN / "frozen_source_identity.json").write_text(json.dumps({"code_sha": code_sha, "base_sha": "c3a2abc9a5246993eabb351d26cfeb51d0270b31", "implementation_files": PRODUCT, "root_owned_dependencies": DEPENDENCIES, "sources": source_identity}, indent=2), encoding="utf-8")
artifact_paths = sorted(path for path in RUN.iterdir() if path.is_file() and path.name != "artifact_manifest.json")
artifact_paths += [ROOT / "reports/tasks/R06-failed-response-persistence.md"]
artifacts = {str(path.relative_to(ROOT)): {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "size_bytes": path.stat().st_size} for path in artifact_paths}
(RUN / "artifact_manifest.json").write_text(json.dumps({"frozen_at": datetime.now().astimezone().isoformat(), "code_sha": code_sha, "artifacts": artifacts}, indent=2), encoding="utf-8")
print(json.dumps({"code_sha": code_sha, "artifacts": len(artifacts), "credential_matches": len(matches), "test_runs": tests}))
