"""Seal a bounded independent recheck without changing the first review or author artifacts."""

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

from prepare_pg import test_connection

run = Path(__file__).parent
root = run.parents[2]
report = root / "reports/reviews/recovery/G-C-R08-aggregate-persistence-review-1-recheck.md"
paths = sorted(path for path in run.iterdir() if path.is_file()
    and path.name not in ("artifact_manifest.json", "secret_scan.json")) + [report]
parsed = test_connection()
secret_values = [value.encode() for value in [parsed.render_as_string(hide_password=False), parsed.password] if value]
findings = [str(path.relative_to(root)) for path in paths if any(secret in path.read_bytes() for secret in secret_values)]
assert not findings, "owned recheck artifacts contain an actual test connection value"
(run / "secret_scan.json").write_text(json.dumps({"checked_files": len(paths), "findings": 0,
    "provider_credentials_read": False, "secret_vault_read": False, "test_connection_emitted": False}), encoding="utf-8")
paths.append(run / "secret_scan.json")
counts = {}
for name, filename in [("author_units", "author_units.xml"), ("author_pg", "author_pg.xml"),
    ("original_pg", "original_pg.xml"), ("independent_pg", "independent_pg.xml")]:
    document = ET.parse(run / filename)
    counts[name] = {"tests": len(document.findall(".//testcase")),
        "failures": len(document.findall(".//failure")), "errors": len(document.findall(".//error")),
        "skipped": len(document.findall(".//skipped"))}
entries = [{"path": str(path.relative_to(root)).replace("\\", "/"),
    "basis": "raw_bytes", "size_bytes": len(path.read_bytes()),
    "sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for path in paths]
manifest = {"schema_version": "r08-aggregate-persistence-review1-recheck1-manifest-1",
    "generated_at": datetime.now(timezone(timedelta(hours=8))).isoformat(), "review_status": "complete",
    "verdict": "Ship; limited service/cache slice; Must 1 closed",
    "reviewed_sha": "a76374ca9200945441a83421050eceef00db47d8",
    "reviewed_tree": subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], cwd=root, text=True).strip(),
    "code_sha": "4a3ba0f384eb15cc64b2e4e9cde33805909c6884",
    "code_tree": subprocess.check_output(["git", "rev-parse", "4a3ba0f384eb15cc64b2e4e9cde33805909c6884^{tree}"], cwd=root, text=True).strip(),
    "author_manifest_sha256": hashlib.sha256((root / "reports/runs/recovery_r08_cache_ttl_fix1_20261016/artifact_manifest.json").read_bytes()).hexdigest(),
    "verification": counts, "current_directed_tests": sum(value["tests"] for value in counts.values()),
    "original_320_rerun": False, "provider_wire_requests": 0, "account_requests": 0, "model_requests": 0,
    "actual_fee": "unknown", "safe_samples_replayed_this_run": 0,
    "production_0019": "not_run", "redis_live": "not_run", "api_worker_ui": "not_run", "files": entries}
(run / "artifact_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
print(json.dumps({"owned_files": len(entries), "verification": counts, "actual_secret_scan_findings": 0,
    "report_sha256": hashlib.sha256(report.read_bytes()).hexdigest(),
    "manifest_sha256": hashlib.sha256((run / "artifact_manifest.json").read_bytes()).hexdigest()}))
