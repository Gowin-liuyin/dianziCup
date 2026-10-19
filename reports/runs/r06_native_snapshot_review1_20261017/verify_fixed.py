"""Check only the fixed public source and Product manifest paths without installing anything."""

import hashlib
import json
import sys
from pathlib import Path

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
manifest_path = ROOT / "reports/runs/r06_native_process_snapshot_20261017/handoff/source_manifest.json"
raw = manifest_path.read_bytes()
manifest = json.loads(raw)
assert hashlib.sha256(raw).hexdigest() == "4d93914833883466dcf728e03c24ab394046a05cf8aab1e5a52e25bff3fae41c"
assert manifest["core_source_sha"] == "c8e94650b921a258e1df4050521d8abee88059ef"
assert manifest["operations_source_sha"] == "fdb40bd56bf06d716f6a6b00b941ce0e03ce06b9"
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
assert hashlib.sha256(pending_path.read_bytes()).hexdigest() == "1a65d235d4774a528153c0199112b54ee01b497d3dbb8059341cfd9b92c82b19"
pending = json.loads(pending_path.read_bytes())
assert pending["ready"] is False and pending["source_job_ledger_offset"] == 42
assert pending["source_database_oid"] is None and pending["source_database_marker_sha256"] is None
activation = json.loads((manifest_path.parent / "activation.pending.json").read_bytes())
flags = ("root_live_authorized", "independent_review_ship", "root_budget_approved", "integrated_key_checks_passed", "actual_kernel_guardian_checked", "fresh_resource_binding_checked", "source_db_oid_binding_approved")
assert all(activation[flag] is False for flag in flags)
result = {"source_manifest_raw_sha256": hashlib.sha256(raw).hexdigest(), "source_23_checked": len(checks), "product_217_raw_checked": 217, "product_raw_git_different_count": sum(not row["raw_equals_git"] for row in manifest["product_files"]), "pending_runtime_hash": hashlib.sha256(pending_path.read_bytes()).hexdigest(), "pending_ready": False, "pending_seven_flags": {flag: activation[flag] for flag in flags}, "pending_is_actual_installation": False, "sources": checks}
(RUN / (sys.argv[1] if len(sys.argv) > 1 else "fixed_verification.json")).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps({key: value for key, value in result.items() if key != "sources"}))
