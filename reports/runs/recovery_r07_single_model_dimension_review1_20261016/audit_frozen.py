"""Validate frozen evidence bytes and source identities without accepting author conclusions."""

import hashlib
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET
from collections import Counter

from review_run import ROOT, RUN

MATERIAL = "b05e63462f1b513eabc183d0a8d42b03196696d2"
CODE = "d8a3189bb7bc1cfde24825f5478920e37eac9556"
BASE = "63e4cafe1363530eb08cdfe7fec56cfc07a81b8a"
AUTHOR = ROOT / "reports/runs/recovery_r07_single_model_dimension_20261016"
AUTHOR_WT = Path("D:/wt/r07-single-field")


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def sha(value):
    return hashlib.sha256(value).hexdigest()


manifest_path = AUTHOR / "material_manifest.json"
manifest_bytes = manifest_path.read_bytes()
assert sha(manifest_bytes) == "9d267434cca417d4a0a8eb3216956473f91b98b49148711e7b9dcb5950d85c0b"
manifest = json.loads(manifest_bytes)
assert manifest["artifact_count"] == len(manifest["artifacts"]) == 164
checked = []
for category in ("sources", "artifacts"):
    for entry in manifest[category]:
        relative = entry["path"]
        raw = (ROOT / relative).read_bytes()
        author_raw = (AUTHOR_WT / relative).read_bytes()
        blob_id = git("rev-parse", f"{MATERIAL}:{relative}").decode().strip()
        blob = git("cat-file", "blob", blob_id)
        assert blob_id == entry["git_blob"], relative
        assert len(blob) == entry["git_blob_size_bytes"], relative
        assert sha(blob) == entry["git_blob_sha256"], relative
        if category == "artifacts":
            assert len(author_raw) == entry["raw_size_bytes"] and sha(author_raw) == entry["raw_sha256"], relative
            assert author_raw == blob, relative
            assert raw.replace(b"\r\n", b"\n") == blob.replace(b"\r\n", b"\n"), relative
        else:
            assert git("rev-parse", f"{CODE}:{relative}").decode().strip() == blob_id, relative
            assert raw.replace(b"\r\n", b"\n") == blob.replace(b"\r\n", b"\n"), relative
        checked.append({"path": relative, "category": category,
            "raw_sha256_review_checkout": sha(raw), "raw_equals_author_raw": sha(raw) == entry["raw_sha256"],
            "author_worktree_raw_sha256": sha(author_raw),
            "material_blob": blob_id, "blob_sha256": sha(blob)})

adjustment = json.loads((AUTHOR / "attribute_adjustment.json").read_text())
old_attributes = git("show", f"{CODE}:.gitattributes")
new_attributes = git("show", f"{MATERIAL}:.gitattributes")
assert sha(old_attributes) == adjustment["old_git_blob_sha256"]
assert new_attributes.startswith(old_attributes)
appended = new_attributes[len(old_attributes):].decode().strip().splitlines()
assert appended == adjustment["rules"]
assert len(adjustment["diff_files"]) == 11
assert len([value for value in appended if value.endswith(" -diff")]) == 11
assert appended[0] == "reports/runs/recovery_r07_single_model_dimension_20261016/** -text"

shared = ["backend/src/ai_intel/infrastructure/models/generation.py",
          "backend/tests/unit/test_r05_generation_predispatch_timeout.py"]
for path in shared:
    assert git("show", f"47c47bc2b5d537166ee47a01c2ab14c035466e3d:{path}") == git("show", f"{BASE}:{path}"), path
    assert git("show", f"{BASE}:{path}") == git("show", f"{MATERIAL}:{path}"), path
assert len(git("diff", "--name-only", BASE, CODE).decode().splitlines()) == 4

summaries = {}
failure_signatures = {}
for filename in ("original_red.xml", "green_draft.xml", "green_draft2.xml", "new_draft_green.xml",
                 "baseline_red.xml", "baseline_red2.xml", "final_review_32.xml"):
    tree = ET.parse(AUTHOR / filename)
    summaries[filename] = [{key: suite.attrib.get(key, "0") for key in ("tests", "failures", "errors", "skipped")}
                          for suite in tree.iter("testsuite")]
    failure_signatures[filename] = dict(Counter(
        item.attrib.get("message", "").splitlines()[0][:220]
        for case in tree.iter("testcase") for item in list(case)
        if item.tag in {"failure", "error"}))
receipt = {"material_sha": MATERIAL, "code_sha": CODE, "effective_baseline_sha": BASE,
    "author_manifest_sha256": sha(manifest_bytes), "artifacts_checked": 164, "sources_checked": 4,
    "all_material_raw_equals_frozen_blob": True, "attribute_rules_added": appended,
    "old_attribute_prefix_preserved": True, "shared_predispatch_code_unchanged": True,
    "source_diff_files": git("diff", "--name-only", BASE, CODE).decode().splitlines(),
    "preserved_author_red_xml": summaries, "author_failure_signatures": failure_signatures,
    "checked": checked}
(RUN / "frozen_audit.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
print(json.dumps({key: value for key, value in receipt.items() if key != "checked"}, ensure_ascii=False, indent=2))
