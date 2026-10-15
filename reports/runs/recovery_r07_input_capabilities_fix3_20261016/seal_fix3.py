"""Seal only new materials and verify that the preceding frozen receipts stay unchanged."""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
PRIOR = ROOT / "reports/runs/recovery_r07_input_capabilities_20261016"
CODE_SHA = "5b3869e4dcdfa16c0ae393cd73acae4cf27efbf9"
ZONE = ZoneInfo("Asia/Shanghai")
previous_bytes = (PRIOR / "fix2_artifact_manifest.json").read_bytes()
assert hashlib.sha256(previous_bytes).hexdigest() == "71d23f1aa47f6e6bdea503d23bbfcd479c000efdb2e6ca494237152d432ce2f9"
previous = json.loads(previous_bytes)
for receipt in previous["files"]:
    raw = (ROOT / receipt["path"]).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == receipt["raw_sha256"]
assert hashlib.sha256((PRIOR / "artifact_manifest.json").read_bytes()).hexdigest() == "8138f507572bedf48d57b6c7e81b398e206feb5f0067847e0f727d7a2e52fb84"
code_paths = [item["path"] for item in previous["code"]] + ["docs/decisions/CR-R07_fix3_scalar_constructor_boundary.md"]
code = []
for relative in code_paths:
    raw = (ROOT / relative).read_bytes()
    blob = subprocess.check_output(["git", "show", CODE_SHA + ":" + relative], cwd=ROOT)
    assert raw.replace(b"\r\n", b"\n") == blob.replace(b"\r\n", b"\n")
    code.append({"path": relative, "bytes": len(raw), "raw_sha256": hashlib.sha256(raw).hexdigest(),
                 "git_blob_sha256": hashlib.sha256(blob).hexdigest(),
                 "lf_normalized_sha256": hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()})
(RUN / "fix3_frozen_code_manifest.json").write_text(json.dumps({"code_sha": CODE_SHA, "files": code}, indent=2), encoding="utf-8")
command = ["git", "diff", "4c339e6f56b302a7081ea230382b8b69ad42c10c", CODE_SHA, "--check"]
started = datetime.now(ZONE).isoformat()
result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
(RUN / "fix3_source_diff_check.log").write_text(result.stdout + result.stderr, encoding="utf-8")
(RUN / "fix3_source_diff_command.json").write_text(json.dumps({
    "command": command, "cwd": str(ROOT), "started_at": started,
    "completed_at": datetime.now(ZONE).isoformat(), "exit_code": result.returncode,
}, indent=2), encoding="utf-8")
assert result.returncode == 0
cas = previous["external_cas"]
for receipt in cas:
    raw = Path(receipt["path"]).read_bytes()
    assert len(raw) == receipt["bytes"] and hashlib.sha256(raw).hexdigest() == receipt["sha256"]
checks = []
for name in ("unit_065327", "contract_065059", "security_065059", "regression_065327",
             "fieldset_065327", "integration_065327", "independent_original_065059",
             "independent_pg_065327", "fixed_original_23", "fixed_first_23"):
    record = json.loads((RUN / (name + ".json")).read_text(encoding="utf-8"))
    assert record["exit_code"] == 0 and record["failed"] == 0 and record["errors"] == 0 and record["skipped"] == 0
    checks.append({"artifact": name, **record})
(RUN / "fix3_verification_summary.json").write_text(json.dumps({
    "code_sha": CODE_SHA, "state": "awaiting_review", "checks": checks,
    "static_commands": "static_commands_065327.json", "paid_calls": 0, "new_network_requests": 0,
    "model_calls": 0, "fee": "unknown", "external_cas": cas,
    "previous_material_sha": "4c339e6f56b302a7081ea230382b8b69ad42c10c",
    "previous_manifest_raw_sha256": hashlib.sha256(previous_bytes).hexdigest(),
    "previous_material_files_verified_unchanged": len(previous["files"]),
    "frontend": "not_run", "e2e": "not_run", "live_model": "not_run", "manual": "not_run",
    "official_full_schema": "failed_preceding_run_not_repeated", "default_app_taxonomy": "not_integrated",
    "graph_shared_pg": "not_run_this_fix_unchanged_code",
}, indent=2), encoding="utf-8")
files = []
paths = [*RUN.rglob("*"), ROOT / "reports/tasks/R07-input-capabilities-fix3.md"]
for path in sorted(paths):
    if not path.is_file() or "__pycache__" in path.parts or path.name in {"fix3_artifact_manifest.json", "fix3_material_fingerprint.json"}:
        continue
    raw = path.read_bytes()
    files.append({"path": str(path.relative_to(ROOT)).replace("\\", "/"), "bytes": len(raw),
                  "raw_sha256": hashlib.sha256(raw).hexdigest(),
                  "lf_normalized_sha256": hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()})
manifest = {"code_sha": CODE_SHA, "created_at": datetime.now(ZONE).isoformat(),
            "code": code, "files": files, "external_cas": cas,
            "prior_manifest_raw_sha256": hashlib.sha256(previous_bytes).hexdigest(),
            "prior_material_files_verified_unchanged": len(previous["files"])}
encoded = json.dumps(manifest, indent=2).encode()
(RUN / "fix3_artifact_manifest.json").write_bytes(encoded)
fingerprint = {"manifest_raw_sha256": hashlib.sha256(encoded).hexdigest(), "code_sha": CODE_SHA,
               "source_files": len(code), "material_files": len(files), "external_cas_objects": len(cas),
               "prior_material_files_verified_unchanged": len(previous["files"])}
(RUN / "fix3_material_fingerprint.json").write_text(json.dumps(fingerprint, indent=2), encoding="utf-8")
print(json.dumps(fingerprint))
