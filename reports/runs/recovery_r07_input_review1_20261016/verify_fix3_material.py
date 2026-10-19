"""Independently verify the new freeze and preserve the preceding material window."""

import hashlib
import importlib
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
AUTHOR = Path("D:/wt/r07-input-capabilities")
SOURCE = "5b3869e4dcdfa16c0ae393cd73acae4cf27efbf9"
PRIOR_SOURCE = "7aeb85ae8277c048fb762dbc705436602cb18f9d"
PRIOR_MATERIAL = "4c339e6f56b302a7081ea230382b8b69ad42c10c"
PRIOR_HASH = "71d23f1aa47f6e6bdea503d23bbfcd479c000efdb2e6ca494237152d432ce2f9"
RELATIVE = "reports/runs/recovery_r07_input_capabilities_fix3_20261016/fix3_artifact_manifest.json"
CAS_HASHES = {"be2a878468f7ae0e04feea70c712b13114017dbf9e8a1b33a70e318311c0b2b3", "f7a7705971796ac26aed238f62594e24ff028549586b37150da32d9bbd58c554", "c9c23971d0db07e2782423d795a20e78d5c2c9bcdc78fc67e24530657daaec41", "17349bf6127b69a2b366aa6c18a8a9d0034545c88186e8120269f94b51f263f1"}
sys.path.insert(0, str(ROOT / "backend/src"))


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def verify_file(item, revision, group):
    author = (AUTHOR / item["path"]).read_bytes()
    reviewer = (ROOT / item["path"]).read_bytes()
    blob = subprocess.check_output(["git", "show", revision + ":" + item["path"]], cwd=ROOT)
    assert len(author) == item["bytes"] and sha(author) == item["raw_sha256"]
    assert sha(reviewer.replace(b"\r\n", b"\n")) == item["lf_normalized_sha256"]
    assert sha(blob.replace(b"\r\n", b"\n")) == item["lf_normalized_sha256"]
    if group == "code":
        assert sha(blob) == item["git_blob_sha256"]
    return {"group": group, "path": item["path"], "revision": revision, "author_raw_matched": True, "reviewer_lf_matched": True, "git_lf_matched": True}


def main():
    material, expected_hash = sys.argv[1:3]
    started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()
    encoded = (AUTHOR / RELATIVE).read_bytes()
    assert sha(encoded) == expected_hash
    manifest = json.loads(encoded)
    assert manifest["code_sha"] == SOURCE
    assert len(manifest["code"]) == 11 and len(manifest["external_cas"]) == 4
    assert manifest["prior_manifest_raw_sha256"] == PRIOR_HASH and manifest["prior_material_files_verified_unchanged"] == 191
    fixed_blob = subprocess.check_output(["git", "show", material + ":" + RELATIVE], cwd=ROOT)
    assert sha(fixed_blob.replace(b"\r\n", b"\n")) == sha(encoded.replace(b"\r\n", b"\n"))
    (RUN / "author_fix3_raw_manifest.json").write_bytes(encoded)
    details = [verify_file(item, SOURCE, "code") for item in manifest["code"]]
    details += [verify_file(item, material, "files") for item in manifest["files"]]
    prior_encoded = (RUN / "author_fix2_raw_manifest.json").read_bytes()
    assert sha(prior_encoded) == PRIOR_HASH
    prior = json.loads(prior_encoded)
    details += [verify_file(item, PRIOR_MATERIAL, "prior_files") for item in prior["files"]]
    for item in manifest["external_cas"]:
        path = Path(item["path"])
        assert path.resolve().parent == Path("D:/dianzi-private/r07-taxonomy-cas").resolve() and path.name in CAS_HASHES
        raw = path.read_bytes()
        assert len(raw) == item["bytes"] and sha(raw) == item["sha256"] == path.name
        details.append({"group": "cas", "path": str(path), "bytes": len(raw), "sha256": sha(raw), "raw_matched": True})
    contract = "docs/decisions/CR-R07_fix3_scalar_constructor_boundary.md"
    frozen_contract = subprocess.check_output(["git", "show", SOURCE + ":" + contract], cwd=ROOT)
    assert frozen_contract.replace(b"\r\n", b"\n") == (ROOT / contract).read_bytes().replace(b"\r\n", b"\n")
    seam = "docs/decisions/CR-R07_context_validation_seam.md"
    assert (Path("D:/dianzi") / seam).read_bytes().replace(b"\r\n", b"\n") == (ROOT / seam).read_bytes().replace(b"\r\n", b"\n")
    modules = {}
    for name in ("evidence_selection", "taxonomy_inputs", "model_fields", "field_sources"):
        module = importlib.import_module("ai_intel.enrichment." + name)
        assert Path(module.__file__).is_relative_to(ROOT)
        modules[name] = module.__file__
    result = {"started_at": started, "completed_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(), "command": [sys.executable, str(Path(__file__).resolve()), material, expected_hash], "cwd": str(ROOT), "exit_code": 0, "source_sha": SOURCE, "material_sha": material, "raw_manifest_sha256": expected_hash, "code_files": 11, "material_files": len(manifest["files"]), "prior_material_files_verified_unchanged": 191, "cas_objects": 4, "all_author_raw_and_fixed_git_lf_verified": True, "fix3_contract_git_bytes_sha256": sha(frozen_contract), "fix3_contract_lf_equal": True, "main_checkout_fix3_contract_present": (Path("D:/dianzi") / contract).exists(), "fix3_authorization": "root directed independent explicit timestamp Must4 Fix3; fixed CR is verified author/reviewer/Git", "root_seam_contract_lf_equal": True, "module_files": modules, "details": details}
    (RUN / "author_fix3_material_verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "details"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
