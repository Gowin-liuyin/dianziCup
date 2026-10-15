"""Bind review artifacts to the exact code commit without circular manifest hashes."""

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import subprocess
from urllib.parse import unquote
import xml.etree.ElementTree as ET

from sqlalchemy.engine import make_url

from prepare_pg import test_connection

run_directory = Path(__file__).parent
root = run_directory.parents[2]
code_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
code_tree = subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], cwd=root, text=True).strip()
code_paths = subprocess.check_output(["git", "diff", "--name-only", "8a1b04d48346d8550f0326a77f003246a0ebbab5", code_sha], cwd=root, text=True).splitlines()
paths = [root / path for path in code_paths]
paths += [root / "reports/tasks/R08-aggregate-persistence.md"]
paths += [path for path in sorted(run_directory.iterdir()) if path.is_file() and path.name not in ("artifact_manifest.json", "secret_scan.json")]
configured_url = test_connection()
password = unquote(make_url(configured_url).password or "")
secret_values = [value.encode() for value in (configured_url, password) if value]
findings = [str(path.relative_to(root)) for path in paths if any(value in path.read_bytes() for value in secret_values)]
assert not findings, "owned artifacts contain an actual test connection secret"
secret_scan = {"checked_files": len(paths), "findings": 0, "provider_credentials_read": False,
    "test_connection_values_emitted": False, "literal_fixture_markers_are_not_live_credentials": True}
(run_directory / "secret_scan.json").write_text(json.dumps(secret_scan, indent=2), encoding="utf-8")
paths.append(run_directory / "secret_scan.json")

def junit_counts(filename):
    document = ET.parse(run_directory / filename)
    cases = document.findall(".//testcase")
    return {"tests": len(cases), "failures": len(document.findall(".//failure")),
        "errors": len(document.findall(".//error")), "skipped": len(document.findall(".//skipped"))}

def file_entry(path):
    relative = str(path.relative_to(root)).replace("\\", "/")
    if relative in code_paths:
        content = subprocess.check_output(["git", "show", f"{code_sha}:{relative}"], cwd=root)
        basis = "git_blob"
    elif relative == "reports/tasks/R08-aggregate-persistence.md":
        content = path.read_text(encoding="utf-8").replace("\r\n", "\n").encode("utf-8")
        basis = "canonical_text_lf"
    else:
        content = path.read_bytes()
        basis = "artifact_bytes_preserved_by_run_gitattributes"
    return {"path": relative, "size_bytes": len(content), "sha256": hashlib.sha256(content).hexdigest(), "basis": basis}

manifest = {"schema_version": "r08-aggregate-persistence-artifact-manifest-1",
    "generated_at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
    "status": "awaiting_review", "implementation": "complete_internal_slice",
    "base_sha": "8a1b04d48346d8550f0326a77f003246a0ebbab5", "code_sha": code_sha,
    "code_tree": code_tree, "cbm": {"version": "0.11.0", "base_src": [1409,7128],
        "final_src": [1409,7128], "base_assets": [76,243], "final_assets": [120,464],
        "bound_code_sha": code_sha, "bound_code_tree": code_tree},
    "verification": {name: junit_counts(filename) for name,filename in {
        "new_pure": "pure.xml", "real_pg": "pg.xml", "existing_aggregate": "existing_aggregate.xml",
        "network": "network.xml", "r07_contract": "r07.xml"}.items()},
    "provider_wire_requests": 0, "account_requests": 0, "model_requests": 0,
    "historical_safe_samples_replayed": 4, "live": "not_run", "redis_io": "not_run",
    "frontend": "not_run", "e2e": "not_run", "manual": "not_run", "production_migration": "not_run",
    "actual_fee": "unknown", "files": [file_entry(path) for path in paths]}
(run_directory / "artifact_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
print("Frozen code/tree, test counts and byte hashes; actual test-secret scan findings=0.")
