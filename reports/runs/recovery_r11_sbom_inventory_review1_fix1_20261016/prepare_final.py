"""最终材料逐字节校验；只新增资源导入副本，原742证据不覆写。"""

import difflib
import gzip
import hashlib
import json
import subprocess
from pathlib import Path

from review_runner_final import ROOT, RUN, now

AUTHOR = ROOT / "reports/runs/recovery_r11_sbom_inventory_privacy_fix1_20261016"
CODE = "6942c65efd5df013c077275cbb6d8cfec3585080"
MATERIAL = "5be873ec38a41955b5a58e9762df4b866a7a9d63"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, check=True).stdout


def main():
    started = now()
    assert git("rev-parse", "HEAD").decode().strip() == MATERIAL
    manifest_raw = (AUTHOR / "artifact_manifest.json").read_bytes()
    assert sha(manifest_raw) == "95536bffce7cdbcf530fdb8d6a05a7a80a28f260a1babf895b211de072a3325b"
    manifest = json.loads(manifest_raw)
    assert manifest["code_commit"] == CODE
    results = []
    for entry in manifest["entries"]:
        path = ROOT / entry["path"]
        if "exact_raw_copy" in entry:
            raw = gzip.decompress((ROOT / entry["exact_raw_copy"]).read_bytes())
            assert git("show", MATERIAL + ":" + entry["path"]) == raw
            mode = "exact_raw_gzip_and_git_lf"
        else:
            raw = path.read_bytes()
            mode = "indexed_exact_bytes"
        assert len(raw) == entry["bytes"] and sha(raw) == entry["sha256"], entry["path"]
        results.append({"path": entry["path"], "mode": mode, "bytes": len(raw), "sha256": sha(raw)})
    proof = json.loads((AUTHOR / "frozen_source_proof.json").read_bytes())
    for entry in proof["sources"]:
        frozen = git("show", CODE + ":" + entry["path"])
        assert sha(frozen) == entry["git_lf_sha256"]
        assert git("hash-object", "--path=" + entry["path"], entry["path"]).decode().strip() == entry["git_blob"]
    baseline_tests = git("ls-tree", "-r", "--name-only", "c0369e6b", "backend/tests").decode().splitlines()
    for path in baseline_tests:
        assert git("rev-parse", "c0369e6b:" + path) == git("rev-parse", CODE + ":" + path)
    assert len(baseline_tests) == 214
    for path in ("sbom_parser.py", "manifest_parser.py", "inventory_models.py", "sbom_persistence_models.py", "inventory_routes.py", "inventory_contracts.py"):
        name = "backend/src/ai_intel/assets/" + path
        assert git("rev-parse", "c0369e6b:" + name) == git("rev-parse", CODE + ":" + name)
    assert sha((RUN / "test_fix1_probes.py").read_bytes()) == "1b6862cd8b1b35572513ff698788768d826d8bfc885146021c66f510bd87a8d5"
    source = ROOT / "backend/tests/integration/test_r11_sbom_inventory_uri_privacy_followup.py"
    original = source.read_text(encoding="utf-8")
    changed = original.replace("from tests.integration.test_r11_sbom_inventory_postgres", "from review_sbom_resource")
    changed = changed.replace("from tests.integration.test_r11_sbom_inventory_uri_privacy", "from review_privacy_resource")
    target = RUN / "resources" / source.name
    target.write_bytes(changed.encode())
    patch = RUN / (source.name + ".resource.patch")
    patch.write_bytes("".join(difflib.unified_diff(original.splitlines(True), changed.splitlines(True))).encode())
    receipt = {
        "start": started, "end": now(), "code_commit": CODE, "material_commit": MATERIAL,
        "author_manifest_sha256": sha(manifest_raw), "verified_entries": results,
        "baseline_tests_blob_unchanged_count": len(baseline_tests),
        "followup_resource": {"source": str(source), "target": str(target), "source_sha256": sha(source.read_bytes()), "copy_sha256": sha(target.read_bytes()), "only_imports_changed": True},
    }
    (RUN / "final_material_verification.json").write_bytes(json.dumps(receipt, indent=2, ensure_ascii=False).encode())
    print(json.dumps({"verified_entries": len(results), "baseline_tests_unchanged": len(baseline_tests), "original13_sha256": sha((RUN / "test_fix1_probes.py").read_bytes())}))


if __name__ == "__main__":
    main()
