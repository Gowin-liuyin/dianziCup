"""Seal independent artifacts and scan actual approved test secrets only in memory."""

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

from prepare_pg import test_connection

run = Path(__file__).parent
root = run.parents[2]
report = root / "reports/reviews/recovery/G-C-R08-aggregate-persistence-review-1.md"
paths = sorted(path for path in run.iterdir() if path.is_file()
    and path.name not in ("artifact_manifest.json", "secret_scan.json")) + [report]
parsed = test_connection()
secret_values = [value.encode() for value in [parsed.render_as_string(hide_password=False), parsed.password] if value]
findings = [str(path.relative_to(root)) for path in paths if any(secret in path.read_bytes() for secret in secret_values)]
assert not findings, "owned review artifacts contain an actual test connection value"
(run / "secret_scan.json").write_text(json.dumps({"checked_files": len(paths), "findings": 0,
    "provider_credentials_read": False, "secret_vault_read": False, "test_connection_emitted": False}), encoding="utf-8")
paths.append(run / "secret_scan.json")
counts = {}
for name, filename in [("new_pure", "pure_final.xml"), ("original_pg", "pg.xml"),
    ("aggregate", "aggregate_final.xml"), ("gateway", "gateway_final.xml"), ("r07", "r07.xml"),
    ("independent_boundaries", "boundaries_final.xml")]:
    document = ET.parse(run / filename)
    counts[name] = {"tests": len(document.findall(".//testcase")),
        "failures": len(document.findall(".//failure")), "errors": len(document.findall(".//error")),
        "skipped": len(document.findall(".//skipped"))}
entries = [{"path": str(path.relative_to(root)).replace("\\", "/"),
    "basis": "raw_bytes", "size_bytes": len(path.read_bytes()),
    "sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for path in paths]
manifest = {"schema_version": "r08-aggregate-persistence-review1-artifact-manifest-1",
    "generated_at": datetime.now(timezone(timedelta(hours=8))).isoformat(), "status": "needs_changes",
    "verdict": "fix 1 first; limited service/cache slice", "reviewed_sha": "6706cd9eeae8bae612fc7e86dff2e2b0416eeaef",
    "reviewed_tree": subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], cwd=root, text=True).strip(),
    "author_manifest_sha256": hashlib.sha256((root / "reports/runs/recovery_r08_aggregate_persistence_20261016/artifact_manifest.json").read_bytes()).hexdigest(),
    "verification": counts, "provider_wire_requests": 0, "account_requests": 0, "model_requests": 0,
    "actual_fee": "unknown", "safe_samples_offline_replayed": 4,
    "production_0019": "not_run", "redis_live": "not_run", "api_worker_ui": "not_run", "files": entries}
(run / "artifact_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
print(json.dumps({"owned_files": len(entries), "verification": counts, "actual_secret_scan_findings": 0,
    "report_sha256": hashlib.sha256(report.read_bytes()).hexdigest(),
    "manifest_sha256": hashlib.sha256((run / "artifact_manifest.json").read_bytes()).hexdigest()}))
