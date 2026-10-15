"""Seal current source and new raw materials while keeping earlier manifests immutable."""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
CODE_SHA = "7aeb85ae8277c048fb762dbc705436602cb18f9d"
ZONE = ZoneInfo("Asia/Shanghai")
code_paths = [
    "backend/src/ai_intel/enrichment/field_sources.py",
    "backend/src/ai_intel/enrichment/evidence_selection.py",
    "backend/src/ai_intel/enrichment/taxonomy_inputs.py",
    "backend/src/ai_intel/enrichment/model_fields.py",
    "backend/tests/unit/test_r07_input_capabilities.py",
    "backend/tests/contract/test_r07_input_selection_codec.py",
    "backend/tests/security/test_r07_input_capabilities_boundary.py",
    "backend/tests/integration/test_r07_input_capabilities_pg.py",
    "docs/decisions/CR-R07_bounded_evidence_and_taxonomy_inputs.md",
    "docs/decisions/CR-R07_context_validation_seam.md",
]
code = []
for relative in code_paths:
    raw = (ROOT / relative).read_bytes()
    blob = subprocess.check_output(["git", "show", CODE_SHA + ":" + relative], cwd=ROOT)
    assert raw.replace(b"\r\n", b"\n") == blob.replace(b"\r\n", b"\n")
    code.append({"path": relative, "bytes": len(raw), "raw_sha256": hashlib.sha256(raw).hexdigest(),
                 "git_blob_sha256": hashlib.sha256(blob).hexdigest(),
                 "lf_normalized_sha256": hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()})
(RUN / "fix2_frozen_code_manifest.json").write_text(json.dumps({"code_sha": CODE_SHA, "files": code}, indent=2), encoding="utf-8")
command = ["git", "diff", "9c4991a218e3d7208d8c314a3992cd6c499e0b4b", CODE_SHA, "--check"]
started = datetime.now(ZONE).isoformat()
result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
(RUN / "fix2_source_diff_check.log").write_text(result.stdout + result.stderr, encoding="utf-8")
(RUN / "fix2_source_diff_command.json").write_text(json.dumps({
    "command": command, "cwd": str(ROOT), "started_at": started,
    "completed_at": datetime.now(ZONE).isoformat(), "exit_code": result.returncode,
}, indent=2), encoding="utf-8")
assert result.returncode == 0
old_manifest = (RUN / "artifact_manifest.json").read_bytes()
assert hashlib.sha256(old_manifest).hexdigest() == "8138f507572bedf48d57b6c7e81b398e206feb5f0067847e0f727d7a2e52fb84"
cas = []
for name in ("taxonomy_fetch_manifest.json", "atlas_new_org_fetch_manifest.json"):
    for receipt in json.loads((RUN / name).read_text(encoding="utf-8")):
        if receipt.get("result") == "fetched":
            raw = Path(receipt["cas_path"]).read_bytes()
            assert hashlib.sha256(raw).hexdigest() == receipt["sha256"]
            cas.append({"path": receipt["cas_path"], "sha256": receipt["sha256"],
                        "bytes": len(raw), "request_uri": receipt["url"], "status": receipt["status"]})
reviewer_inputs = []
for name in ("test_review_probe.py", "test_review_probe_pg.py"):
    origin = Path("D:/wt/r07-input-review1/reports/runs/recovery_r07_input_review1_20261016") / name
    raw = origin.read_bytes()
    snapshot = RUN / ("fix2_original_" + name)
    snapshot.write_bytes(raw)
    reviewer_inputs.append({"origin": str(origin), "snapshot": snapshot.name,
                            "bytes": len(raw), "raw_sha256": hashlib.sha256(raw).hexdigest()})
chosen = ["unit_062751", "contract_063100", "security_063100", "integration_063544",
          "regression_062906", "fieldset_063100", "graph_062906", "independent_original_062802",
          "independent_pg_062953", "shared_pg_062953"]
checks = []
for name in chosen:
    record = json.loads((RUN / (name + ".json")).read_text(encoding="utf-8"))
    assert record["exit_code"] == 0 and record["failed"] == 0 and record["errors"] == 0 and record["skipped"] == 0
    checks.append({"artifact": name, **record})
(RUN / "fix2_verification_summary.json").write_text(json.dumps({
    "code_sha": CODE_SHA, "state": "awaiting_review", "checks": checks,
    "static_commands": "static_commands_062906.json", "reviewer_original_inputs": reviewer_inputs,
    "frontend": "not_run", "e2e": "not_run", "live_model": "not_run", "manual": "not_run",
    "official_full_schema": "failed", "default_app_taxonomy": "not_integrated",
    "paid_calls": 0, "new_network_requests": 0, "fee": "unknown", "external_cas": cas,
    "initial_manifest_raw_sha256": hashlib.sha256(old_manifest).hexdigest(),
}, indent=2), encoding="utf-8")
files = []
paths = [*RUN.rglob("*"), ROOT / "reports/tasks/R07-input-capabilities.md",
         ROOT / "reports/tasks/R07-input-capabilities-fix2.md"]
for path in sorted(paths):
    if not path.is_file() or path.name in {"fix2_artifact_manifest.json", "fix2_material_fingerprint.json"}:
        continue
    assert "__pycache__" not in path.parts
    raw = path.read_bytes()
    files.append({"path": str(path.relative_to(ROOT)).replace("\\", "/"), "bytes": len(raw),
                  "raw_sha256": hashlib.sha256(raw).hexdigest(),
                  "lf_normalized_sha256": hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()})
manifest = {"code_sha": CODE_SHA, "created_at": datetime.now(ZONE).isoformat(),
            "code": code, "files": files, "external_cas": cas}
encoded = json.dumps(manifest, indent=2).encode()
(RUN / "fix2_artifact_manifest.json").write_bytes(encoded)
fingerprint = {"manifest_raw_sha256": hashlib.sha256(encoded).hexdigest(), "code_sha": CODE_SHA,
               "source_files": len(code), "material_files": len(files), "external_cas_objects": len(cas)}
(RUN / "fix2_material_fingerprint.json").write_text(json.dumps(fingerprint, indent=2), encoding="utf-8")
print(json.dumps(fingerprint))
