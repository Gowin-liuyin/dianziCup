"""逐blob核对作者49项原材料与manifest本体，分列原字节、EOL及期望hash。"""

import hashlib
import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
MATERIAL = "df0faafb64327be190803089f0058f9b5dc2427b"
CODE = "47c47bc2b5d537166ee47a01c2ab14c035466e3d"
AUTHOR_RUN = "reports/runs/recovery_r05_generation_predispatch_timeout_fix_20261016"
MANIFEST = AUTHOR_RUN + "/artifact_manifest.json"


def digest(value):
    return hashlib.sha256(value).hexdigest()


def git_bytes(path, revision=MATERIAL):
    return subprocess.check_output(["git", "show", revision + ":" + path], cwd=ROOT)


def record(path, expected=None):
    raw = (ROOT / path).read_bytes()
    blob = git_bytes(path)
    return {
        "path": path, "raw_sha256": digest(raw), "raw_bytes": len(raw),
        "git_blob_id": subprocess.check_output(["git", "rev-parse", MATERIAL + ":" + path], cwd=ROOT, text=True).strip(),
        "git_blob_sha256": digest(blob), "git_blob_bytes": len(blob),
        "expected_sha256": expected, "expected_matches_raw": expected is None or expected == digest(raw),
        "expected_matches_blob": expected is None or expected == digest(blob),
        "raw_equals_blob": raw == blob,
        "eol_only_difference": raw != blob and raw.replace(b"\r\n", b"\n") == blob.replace(b"\r\n", b"\n"),
        "raw_crlf_count": raw.count(b"\r\n"), "blob_crlf_count": blob.count(b"\r\n"),
    }


manifest = json.loads((ROOT / MANIFEST).read_bytes())
body = record(MANIFEST, "37305c851f70c9c1058e660146c28b2a236a22ddc622424aebb706aaf6ea6ea4")
items = [record(item["path"], item["sha256"]) for item in manifest["artifacts"]]
for item, expected in zip(items, manifest["artifacts"], strict=True):
    item["expected_bytes"] = expected["bytes"]
    item["expected_bytes_match_raw"] = item["raw_bytes"] == expected["bytes"]
unresolved = [item["path"] for item in [body, *items] if not (item["expected_matches_raw"] or item["expected_matches_blob"]) or not (item["raw_equals_blob"] or item["eol_only_difference"])]
source_paths = ["backend/src/ai_intel/infrastructure/models/generation.py", "backend/tests/unit/test_r05_generation_predispatch_timeout.py"]
sources = [{"path": path, "code_blob_sha256": digest(git_bytes(path, CODE)), "material_blob_sha256": digest(git_bytes(path)), "raw_sha256": digest((ROOT / path).read_bytes()), "code_equals_material_blob": git_bytes(path, CODE) == git_bytes(path)} for path in source_paths]
suite_counts = {}
from xml.etree import ElementTree
for case in ElementTree.parse(RUN / "regression.xml").iter("testcase"):
    name = case.attrib["classname"]
    layer = next(layer for layer in ("unit", "contract", "security") if name.startswith("tests." + layer + "."))
    suite_counts[layer] = suite_counts.get(layer, 0) + 1
result = {"recorded_at": datetime.now(timezone(timedelta(hours=8))).isoformat(), "material_sha": MATERIAL, "code_sha": CODE, "manifest_body": body, "artifacts": items, "artifact_count": len(items), "unresolved": unresolved, "raw_equals_blob_count": sum(item["raw_equals_blob"] for item in items), "eol_only_difference_count": sum(item["eol_only_difference"] for item in items), "sources": sources, "regression_layers": suite_counts, "original_red": json.loads((ROOT / AUTHOR_RUN / "red.json").read_bytes()), "source_subtree": subprocess.check_output(["git", "rev-parse", MATERIAL + ":backend/src"], cwd=ROOT, text=True).strip()}
(RUN / "author_material_audit.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="")
print(json.dumps({"artifact_count": len(items), "unresolved": unresolved, "manifest": body, "layers": suite_counts, "sources": sources}, ensure_ascii=False))
assert len(items) == 49 and not unresolved
assert all(item["code_equals_material_blob"] for item in sources)
