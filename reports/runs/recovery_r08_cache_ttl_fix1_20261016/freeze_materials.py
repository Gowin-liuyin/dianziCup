"""Freeze only the TTL fix's code and owned evidence, preserving the old review artifacts."""

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

from sqlalchemy.engine import make_url

from prepare_pg import test_connection

BASE_SHA = "6706cd9eeae8bae612fc7e86dff2e2b0416eeaef"
CODE_SHA = "4a3ba0f384eb15cc64b2e4e9cde33805909c6884"
run_directory = Path(__file__).parent
root = run_directory.parents[2]
code_tree = subprocess.check_output(["git", "rev-parse", f"{CODE_SHA}^{{tree}}"], cwd=root, text=True).strip()
code_paths = subprocess.check_output(["git", "diff", "--name-only", BASE_SHA, CODE_SHA], cwd=root, text=True).splitlines()
paths = [root / path for path in code_paths]
paths += [root / "reports/tasks/R08-cache-ttl-fix1.md"]
paths += [path for path in sorted(run_directory.iterdir()) if path.is_file() and path.name not in ("artifact_manifest.json", "secret_scan.json")]
configured_url = test_connection()
password = make_url(configured_url).password or ""
secret_values = [value.encode() for value in (configured_url, password) if value]
assert not [path for path in paths if any(value in path.read_bytes() for value in secret_values)], "actual test credential found in owned evidence"
(run_directory / "secret_scan.json").write_text(json.dumps({"checked_files": len(paths), "findings": 0,
    "provider_credentials_read": False, "test_connection_values_emitted": False}, indent=2), encoding="utf-8")
paths.append(run_directory / "secret_scan.json")

def file_entry(path):
    relative = str(path.relative_to(root)).replace("\\", "/")
    if relative in code_paths:
        content = subprocess.check_output(["git", "show", f"{CODE_SHA}:{relative}"], cwd=root)
        basis = "git_blob"
    elif relative == "reports/tasks/R08-cache-ttl-fix1.md":
        content = path.read_text(encoding="utf-8").replace("\r\n", "\n").encode()
        basis = "canonical_text_lf"
    else:
        content = path.read_bytes()
        basis = "artifact_bytes_preserved_by_run_gitattributes"
    return {"path": relative, "size_bytes": len(content), "sha256": hashlib.sha256(content).hexdigest(), "basis": basis}

def junit_counts(filename):
    document = ET.parse(run_directory / filename)
    return {"tests": len(document.findall(".//testcase")), "failures": len(document.findall(".//failure")),
        "errors": len(document.findall(".//error")), "skipped": len(document.findall(".//skipped"))}

manifest = {"schema_version": "r08-cache-ttl-fix1-artifact-manifest-1",
    "generated_at": datetime.now(timezone(timedelta(hours=8))).isoformat(), "status": "awaiting_review",
    "base_sha": BASE_SHA, "code_sha": CODE_SHA, "code_tree": code_tree,
    "verification": {name: junit_counts(filename) for name, filename in {
        "red": "unit_red.xml", "targeted_units": "targeted_units.xml", "real_pg": "pg.xml"}.items()},
    "original_320_rerun": False, "provider_wire_requests": 0, "account_requests": 0, "model_requests": 0,
    "actual_fee": "unknown", "production_migration": "not_run", "redis_io": "not_run", "live": "not_run",
    "frontend": "not_run", "e2e": "not_run", "manual": "not_run", "full_r08_implementation": "partial",
    "cbm": {"version": "0.11.0", "src": [1409,7128], "assets_before": [120,464], "assets_after": [120,463],
        "bound_code_sha": CODE_SHA, "bound_code_tree": code_tree}, "files": [file_entry(path) for path in paths]}
(run_directory / "artifact_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
print("TTL fix code/tree and owned evidence frozen; actual test-secret findings=0.")
