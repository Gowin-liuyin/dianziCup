"""Freeze source bytes, original red observation, CAS receipts and actual check metadata."""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
CODE_SHA = "7dae1d82363d8459f3546fee4b92137559dcb5aa"
code_paths = subprocess.check_output([
    "git", "diff-tree", "--no-commit-id", "--name-only", "-r", CODE_SHA,
], cwd=ROOT, text=True).splitlines()
code = []
for relative in code_paths:
    raw = (ROOT / relative).read_bytes()
    blob = subprocess.check_output(["git", "show", CODE_SHA + ":" + relative], cwd=ROOT)
    assert raw.replace(b"\r\n", b"\n") == blob.replace(b"\r\n", b"\n")
    code.append({"path": relative, "bytes": len(raw), "raw_sha256": hashlib.sha256(raw).hexdigest(),
                 "git_blob_sha256": hashlib.sha256(blob).hexdigest(),
                 "lf_normalized_sha256": hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()})
(RUN / "frozen_code_manifest.json").write_text(json.dumps({"code_sha": CODE_SHA, "files": code}, indent=2))
prior_path = Path("D:/wt/r07-enrichment-execution/reports/runs/recovery_r07_enrichment_execution_20261016/nvd_input_budget_observation.json")
prior_bytes = prior_path.read_bytes()
(RUN / "prior_595_nvd_input_budget_observation.json").write_bytes(prior_bytes)
prior = {"source_path": str(prior_path), "source_code_sha": "595e42a91a830f78fd11d0e4fc7a79a1aaf767cb",
         "raw_sha256": hashlib.sha256(prior_bytes).hexdigest(), "copied_without_change": True}
cas = []
for name in ("taxonomy_fetch_manifest.json", "atlas_new_org_fetch_manifest.json"):
    for receipt in json.loads((RUN / name).read_text()):
        if receipt.get("result") == "fetched":
            raw = Path(receipt["cas_path"]).read_bytes()
            assert hashlib.sha256(raw).hexdigest() == receipt["sha256"]
            cas.append({"path": receipt["cas_path"], "sha256": receipt["sha256"],
                        "bytes": len(raw), "request_uri": receipt["url"], "status": receipt["status"]})
checks = []
for path in sorted(RUN.glob("*.json")):
    if path.stem.split("_")[0] in {"unit", "contract", "integration", "security", "regression", "fieldset"}:
        record = json.loads(path.read_text())
        if isinstance(record, dict) and "command" in record:
            checks.append({"artifact": path.name, **record})
(RUN / "verification_summary.json").write_text(json.dumps({
    "code_sha": CODE_SHA, "state": "awaiting_review", "checks": checks,
    "frontend": "not_run", "e2e": "not_run", "live_model": "not_run", "manual": "not_run",
    "official_full_schema": "failed", "default_app_taxonomy": "not_integrated",
    "prior_red": prior, "external_cas": cas,
}, indent=2), encoding="utf-8")
files = []
for path in sorted([*RUN.rglob("*"), ROOT / "reports/tasks/R07-input-capabilities.md"]):
    if not path.is_file() or path.name in {"artifact_manifest.json", "material_fingerprint.json"}:
        continue
    raw = path.read_bytes()
    files.append({"path": str(path.relative_to(ROOT)).replace("\\", "/"), "bytes": len(raw),
                  "raw_sha256": hashlib.sha256(raw).hexdigest(),
                  "lf_normalized_sha256": hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()})
manifest = {"code_sha": CODE_SHA, "created_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
            "code": code, "files": files, "external_cas": cas}
encoded = json.dumps(manifest, indent=2).encode()
(RUN / "artifact_manifest.json").write_bytes(encoded)
(RUN / "material_fingerprint.json").write_text(json.dumps({
    "manifest_raw_sha256": hashlib.sha256(encoded).hexdigest(), "code_sha": CODE_SHA,
    "source_files": len(code), "material_files": len(files), "external_cas_objects": len(cas),
}, indent=2))
print(json.dumps({"code_sha": CODE_SHA, "source_files": len(code), "material_files": len(files),
                  "external_cas_objects": len(cas), "manifest_sha256": hashlib.sha256(encoded).hexdigest()}))
