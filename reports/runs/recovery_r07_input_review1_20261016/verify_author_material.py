"""Verify fixed Git blobs, byte-preserved author materials and four approved CAS objects."""

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
CODE = "7dae1d82363d8459f3546fee4b92137559dcb5aa"
MATERIAL = "eb6daced5f2467dc56ade15857e60a1af9486db0"
REL = "reports/runs/recovery_r07_input_capabilities_20261016"
sys.path.insert(0, str(ROOT / "backend/src"))


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()
    original_manifest = (AUTHOR / REL / "artifact_manifest.json").read_bytes()
    manifest = json.loads(original_manifest)
    original_expected = "8138f507572bedf48d57b6c7e81b398e206feb5f0067847e0f727d7a2e52fb84"
    assert sha(original_manifest) == original_expected
    (RUN / "author_7dae_raw_manifest.json").write_bytes(original_manifest)
    details = []
    for item in manifest["code"]:
        git_bytes = subprocess.check_output(["git", "show", CODE + ":" + item["path"]], cwd=ROOT)
        assert sha(git_bytes) == item["git_blob_sha256"]
        reviewer_bytes = (ROOT / item["path"]).read_bytes()
        assert sha(reviewer_bytes.replace(b"\r\n", b"\n")) == item["lf_normalized_sha256"]
        author_bytes = (AUTHOR / item["path"]).read_bytes()
        details.append({"group": "code", "path": item["path"], "fixed_git_blob_matched": True, "reviewer_lf_matched": True, "author_current_raw_matched": sha(author_bytes) == item["raw_sha256"]})
    for item in manifest["files"]:
        author_bytes = (AUTHOR / item["path"]).read_bytes()
        git_bytes = subprocess.check_output(["git", "show", MATERIAL + ":" + item["path"]], cwd=ROOT)
        assert sha(git_bytes.replace(b"\r\n", b"\n")) == item["lf_normalized_sha256"]
        reviewer_bytes = (ROOT / item["path"]).read_bytes()
        assert sha(reviewer_bytes.replace(b"\r\n", b"\n")) == item["lf_normalized_sha256"]
        details.append({"group": "material", "path": item["path"], "fixed_git_lf_matched": True, "reviewer_lf_matched": True, "author_current_raw_matched": sha(author_bytes) == item["raw_sha256"]})
    for item in manifest["external_cas"]:
        raw = Path(item["path"]).read_bytes()
        assert len(raw) == item["bytes"] and sha(raw) == item["sha256"]
        details.append({"group": "cas", "path": item["path"], "bytes": len(raw), "fixed_raw_matched": True, "sha256": item["sha256"]})
    modules = {}
    for name in ("evidence_selection", "taxonomy_inputs", "model_fields"):
        module = importlib.import_module("ai_intel.enrichment." + name)
        assert Path(module.__file__).is_relative_to(ROOT)
        modules[name] = module.__file__
    import yaml
    assert yaml.__version__ == "6.0.3"
    result = {"started_at": started, "completed_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(), "code_sha": CODE, "material_sha": MATERIAL, "raw_manifest_sha256": sha(original_manifest), "raw_manifest_verified": True, "code_files": len(manifest["code"]), "material_files": len(manifest["files"]), "cas_objects": len(manifest["external_cas"]), "raw_mismatches_after_author_followup": [item for item in details if item.get("author_current_raw_matched") is False], "imports": modules, "pyyaml": yaml.__version__, "details": details}
    (RUN / "author_7dae_material_verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "details"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
