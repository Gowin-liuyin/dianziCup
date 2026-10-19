"""Verify final author raw/LF/Git evidence, approved CAS, contract and untouched shared boundaries."""

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
SOURCE = "7aeb85ae8277c048fb762dbc705436602cb18f9d"
MATERIAL = "4c339e6f56b302a7081ea230382b8b69ad42c10c"
RELATIVE = "reports/runs/recovery_r07_input_capabilities_20261016"
MANIFEST_HASH = "71d23f1aa47f6e6bdea503d23bbfcd479c000efdb2e6ca494237152d432ce2f9"
CAS_HASHES = {"be2a878468f7ae0e04feea70c712b13114017dbf9e8a1b33a70e318311c0b2b3", "f7a7705971796ac26aed238f62594e24ff028549586b37150da32d9bbd58c554", "c9c23971d0db07e2782423d795a20e78d5c2c9bcdc78fc67e24530657daaec41", "17349bf6127b69a2b366aa6c18a8a9d0034545c88186e8120269f94b51f263f1"}
sys.path.insert(0, str(ROOT / "backend/src"))


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()
    encoded = (AUTHOR / RELATIVE / "fix2_artifact_manifest.json").read_bytes()
    assert sha(encoded) == MANIFEST_HASH
    manifest = json.loads(encoded)
    assert manifest["code_sha"] == SOURCE
    assert len(manifest["code"]) == 10 and len(manifest["files"]) == 191 and len(manifest["external_cas"]) == 4
    (RUN / "author_fix2_raw_manifest.json").write_bytes(encoded)
    details = []
    for group in ("code", "files"):
        revision = SOURCE if group == "code" else MATERIAL
        for item in manifest[group]:
            author = (AUTHOR / item["path"]).read_bytes()
            reviewer = (ROOT / item["path"]).read_bytes()
            blob = subprocess.check_output(["git", "show", revision + ":" + item["path"]], cwd=ROOT)
            assert len(author) == item["bytes"] and sha(author) == item["raw_sha256"]
            assert sha(reviewer.replace(b"\r\n", b"\n")) == item["lf_normalized_sha256"]
            assert sha(blob.replace(b"\r\n", b"\n")) == item["lf_normalized_sha256"]
            if group == "code":
                assert sha(blob) == item["git_blob_sha256"]
            details.append({"group": group, "path": item["path"], "author_raw_matched": True, "reviewer_lf_matched": True, "git_lf_matched": True})
    for item in manifest["external_cas"]:
        path = Path(item["path"])
        assert path.resolve().parent == Path("D:/dianzi-private/r07-taxonomy-cas").resolve() and path.name in CAS_HASHES
        raw = path.read_bytes()
        assert len(raw) == item["bytes"] and sha(raw) == item["sha256"] == path.name
        details.append({"group": "cas", "path": str(path), "bytes": len(raw), "sha256": sha(raw), "raw_matched": True})
    untouched = ("backend/src/ai_intel/enrichment/contracts.py", "backend/src/ai_intel/enrichment/inputs.py", "backend/src/ai_intel/enrichment/publication.py", "backend/src/ai_intel/knowledge/evidence_graph.py", "backend/tests/unit/test_r07_model_fields.py", "backend/tests/unit/test_r07_single_model_dimension.py", "backend/tests/unit/test_r07_model_field_root_causes.py", "backend/pyproject.toml", "backend/uv.lock")
    for relative in untouched:
        original = subprocess.check_output(["git", "show", "7dae1d82^:" + relative], cwd=ROOT)
        final = subprocess.check_output(["git", "show", SOURCE + ":" + relative], cwd=ROOT)
        assert original == final
    contract_path = "docs/decisions/CR-R07_context_validation_seam.md"
    root_contract = (Path("D:/dianzi") / contract_path).read_bytes()
    reviewed_contract = (ROOT / contract_path).read_bytes()
    assert root_contract.replace(b"\r\n", b"\n") == reviewed_contract.replace(b"\r\n", b"\n")
    modules = {}
    for name in ("evidence_selection", "taxonomy_inputs", "model_fields", "field_sources"):
        module = importlib.import_module("ai_intel.enrichment." + name)
        assert Path(module.__file__).is_relative_to(ROOT)
        modules[name] = module.__file__
    result = {"started_at": started, "completed_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(), "source_sha": SOURCE, "material_sha": MATERIAL, "raw_manifest_sha256": MANIFEST_HASH, "code_files": 10, "material_files": 191, "cas_objects": 4, "all_author_raw_and_fixed_git_lf_verified": True, "unchanged_contract_and_regression_files": list(untouched), "root_seam_contract_raw_sha256": sha(root_contract), "root_seam_contract_lf_equal": True, "module_files": modules, "details": details}
    (RUN / "author_fix2_material_verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "details"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
