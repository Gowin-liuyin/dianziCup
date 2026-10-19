"""Check only the fixed public source and Product manifest paths without installing anything."""

import hashlib
import json
import sys
from pathlib import Path

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
manifest_path = ROOT / "reports/runs/r06_native_process_snapshot_bound_fix2_20261017/handoff/source_manifest.json"
raw = manifest_path.read_bytes()
manifest = json.loads(raw)
assert hashlib.sha256(raw).hexdigest() == "6a1f1cccb510dffe00fa379166d2f423731baf67fa124853493d3b347f80ba55"
assert manifest["core_source_sha"] == "37ffe6da1d9a258359363d42488d236b7c00ad87"
assert manifest["operations_source_sha"] == "81053fd680dbfb275bfcc511ae44f573340efd56"
assert manifest["product_sha"] == "912d8b381eaab9260ead30d68f49b88fa8078384"
assert len(manifest["source_23"]) == 23 and len(manifest["product_files"]) == 217
checks = []
for row in manifest["source_23"]:
    source = (ROOT / row["candidate_path"]).read_bytes()
    assert len(source) == row["candidate_raw"]["bytes"]
    assert hashlib.sha256(source).hexdigest() == row["candidate_raw"]["sha256"]
    checks.append({"path": row["candidate_path"], "bytes": len(source), "sha256": hashlib.sha256(source).hexdigest()})
product = Path(manifest["product_root"])
for row in manifest["product_files"]:
    source = (product / row["path"]).read_bytes()
    assert len(source) == row["raw"]["bytes"]
    assert hashlib.sha256(source).hexdigest() == row["raw"]["sha256"]
pending_path = manifest_path.parent / "runtime_binding.pending.json"
assert hashlib.sha256(pending_path.read_bytes()).hexdigest() == "9be80e1c0bbed25c2cdcb352d5b38158d01d127e929a290500dbf0576f99287a"
pending = json.loads(pending_path.read_bytes())
assert pending["ready"] is False and pending["source_job_ledger_offset"] == 42
assert pending["source_database_oid"] is None and pending["source_database_marker_sha256"] is None
activation = json.loads((manifest_path.parent / "activation.pending.json").read_bytes())
flags = ("root_live_authorized", "independent_review_ship", "root_budget_approved", "integrated_key_checks_passed", "actual_kernel_guardian_checked", "fresh_resource_binding_checked", "source_db_oid_binding_approved")
assert all(activation[flag] is False for flag in flags)
result = {"source_manifest_raw_sha256": hashlib.sha256(raw).hexdigest(), "source_23_checked": len(checks), "product_217_raw_checked": 217, "product_raw_git_different_count": sum(not row["raw_equals_git"] for row in manifest["product_files"]), "pending_runtime_hash": hashlib.sha256(pending_path.read_bytes()).hexdigest(), "pending_ready": False, "pending_seven_flags": {flag: activation[flag] for flag in flags}, "pending_is_actual_installation": False, "sources": checks}
(RUN / (sys.argv[1] if len(sys.argv) > 1 else "fixed_verification.json")).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps({key: value for key, value in result.items() if key != "sources"}))
