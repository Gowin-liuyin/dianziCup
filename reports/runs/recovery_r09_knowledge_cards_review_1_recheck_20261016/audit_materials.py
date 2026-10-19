"""按清单真实schema逐原始字节与固定Git blob核验；不修改任何旧材料。"""

import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
FIXED = "b5ca278d739feac5dba9ca3e693d538a5a8d475e"
CODE = "dd36cf78c3d15138683d09c12ea867c0055b9674"
BASE = "ed217564e9cf3571b430d0fe7caa4d3999c7320b"
SHARED = "47c47bc2b5d537166ee47a01c2ab14c035466e3d"
OLD_ROOT = Path("C:/Users/yinha/.codex/worktrees/r09-knowledge-cards-review-1/dianzi")
OLD_RUN = "reports/runs/recovery_r09_knowledge_cards_review_1_20261016"


def digest(value):
    return hashlib.sha256(value).hexdigest()


def git(*arguments):
    return subprocess.check_output(["git", *arguments], cwd=ROOT)


def blob(path, revision=FIXED):
    return git("show", f"{revision}:{path}")


def fixed_bundle(name, relative_path, expected_body, expected_count, original_base=False):
    manifest_raw = (ROOT / relative_path).read_bytes()
    manifest_blob = blob(relative_path)
    assert expected_body in {digest(manifest_raw), digest(manifest_blob)}, name
    manifest = json.loads(manifest_raw)
    assert "files" in manifest
    entries = manifest["files"]
    assert len(entries) == expected_count
    rows = []
    for item in entries:
        path = item["path"]
        assert not Path(path).is_absolute() and ".." not in Path(path).parts
        raw = (ROOT / path).read_bytes()
        stored = blob(path)
        matches = []
        if digest(raw) == item["sha256"]:
            matches.append("checkout_raw")
        if digest(stored) == item["sha256"]:
            matches.append("fixed_git_blob")
        if not matches:
            for label, variant in (("expected_crlf", stored.replace(b"\n", b"\r\n")), ("expected_lf", stored.replace(b"\r\n", b"\n"))):
                if digest(variant) == item["sha256"]:
                    matches.append(label)
        assert matches, (name, path)
        relationship = "byte_identical" if raw == stored else "different_bytes"
        if raw != stored and stored.replace(b"\n", b"\r\n") == raw:
            relationship = "checkout_crlf_only"
        base_blob_equal = None
        if original_base:
            base_blob_equal = stored == blob(path, BASE)
            assert base_blob_equal, path
        rows.append({"path": path, "expected_sha256": item["sha256"], "checkout_raw_sha256": digest(raw), "fixed_git_blob_sha256": digest(stored), "raw_size": len(raw), "blob_size": len(stored), "manifest_matches": matches, "raw_blob_relationship": relationship, "base_blob_equal": base_blob_equal})
    return {"manifest_raw_sha256": digest(manifest_raw), "manifest_blob_sha256": digest(manifest_blob), "actual_schema": "files[path,sha256]", "entries": len(rows), "matches": dict(Counter(value for row in rows for value in row["manifest_matches"])), "eol": dict(Counter(row["raw_blob_relationship"] for row in rows)), "files": rows}


def raw_bundle(name, root, relative_path, key, expected_body, expected_count):
    body = (root / relative_path).read_bytes()
    assert digest(body) == expected_body, name
    manifest = json.loads(body)
    entries = manifest[key]
    assert len(entries) == expected_count
    rows = []
    for item in entries:
        path = item["path"]
        assert not Path(path).is_absolute() and ".." not in Path(path).parts
        assert path.startswith("reports/runs/") or path.startswith("reports/reviews/"), path
        raw = (root / path).read_bytes()
        assert digest(raw) == item["sha256"], (name, path)
        rows.append({"path": path, "raw_sha256": digest(raw), "size_bytes": len(raw), "matches": True})
    return {"manifest_raw_sha256": digest(body), "root": str(root), "actual_schema": key + "[path,sha256]", "entries": len(rows), "files": rows}


assert git("rev-parse", "HEAD").decode().strip() == FIXED
changed = git("diff", "--name-only", BASE, FIXED, "--", "backend/src", "backend/tests").decode().splitlines()
expected_changes = ["backend/src/ai_intel/infrastructure/models/generation.py", "backend/tests/unit/test_r05_generation_predispatch_timeout.py"]
assert changed == expected_changes
bindings = []
for path in changed:
    source, code, fixed = blob(path, SHARED), blob(path, CODE), blob(path)
    assert source == code == fixed
    bindings.append({"path": path, "shared_code_combo_git_blobs_equal": True, "git_blob_sha256": digest(fixed), "checkout_raw_sha256": digest((ROOT / path).read_bytes())})
material_changes = git("diff", "--name-only", CODE, FIXED).decode().splitlines()
assert all(path == ".gitattributes" or path == "reports/tasks/R09-shared-timeout-combination.md" or path.startswith("reports/runs/recovery_r09_shared_timeout_combination_20261016/") for path in material_changes)
assert git("diff", BASE, FIXED, "--", "docs", "progress", "contracts", "backend/uv.lock", "backend/pyproject.toml") == b""
result = {
    "fixed_sha": FIXED,
    "code_sha": CODE,
    "code_tree": git("rev-parse", CODE + "^{tree}").decode().strip(),
    "code_changes": changed,
    "code_bindings": bindings,
    "material_change_count": len(material_changes),
    "original_author_90": fixed_bundle("original_author_90", "reports/runs/recovery_r09_knowledge_cards_20261016/artifact_manifest.json", "816eaf1ae985e07c35c1fee5753576d6e7ca43f6bd526cbe756dbc7914fb790f", 90, True),
    "combination_129": fixed_bundle("combination_129", "reports/runs/recovery_r09_shared_timeout_combination_20261016/artifact_manifest.json", "a851dbef8b38575aadf13ca08cae099418d051c11004adc2a98d9747422e28ac", 129),
    "original_r09_review_121": raw_bundle("original_r09_review_121", OLD_ROOT, OLD_RUN + "/artifact_manifest.json", "files", "d8eb2e34edf1199224778c58b31a13622715854014907b59ea315e9fc8631fba", 121),
    "shared_generation_review_121": raw_bundle("shared_generation_review_121", Path("D:/dianzi"), "reports/runs/recovery_r05_generation_predispatch_timeout_review_1_20261016/artifact_manifest.json", "artifacts", "6b4a9062c1aeb9fb042b58e8ead1b30c4c63798a2b5dbb79361cdd3b33b260f0", 121),
}
baseline = ET.parse(OLD_ROOT / OLD_RUN / "independent_boundaries_sqlite_final.xml")
cases = baseline.findall(".//testcase")
failed = [case.get("name") for case in cases if case.find("failure") is not None]
assert len(cases) == 17 and failed == ["test_expired_client_deadline_is_error_with_one_attempt"]
result["verified_original_baseline"] = {"tests": 17, "passed": 16, "failed": failed, "rerun_in_this_turn": False, "old_raw_manifest_preserved": True}
(RUN / "materials_audit.json").write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode())
print(json.dumps({key: ({name: value for name, value in item.items() if name != "files"} if isinstance(item, dict) else item) for key, item in result.items()}, ensure_ascii=False, indent=2))
