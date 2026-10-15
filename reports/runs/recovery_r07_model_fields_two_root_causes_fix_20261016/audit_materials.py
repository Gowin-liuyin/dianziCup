"""Audit only bounded named evidence, source files and unchanged reviewer test copies."""

import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
BASE = "6199ad193d36da17c6597ee286aae40af887d425"
ORIGINAL = Path("D:/wt/r07-model-fields")
REVIEW = Path("D:/wt/r07-model-fields-review-1/reports/runs/recovery_r07_model_fields_review_1_20261016")


def digest(content):
    return hashlib.sha256(content).hexdigest()


def blob(commit, path):
    return subprocess.check_output(["git", "show", commit + ":" + path], cwd=ROOT)


manifest_path = "reports/runs/recovery_r07_model_fields_20261016/artifact_manifest.json"
manifest = json.loads(blob(BASE, manifest_path))
artifacts = []
for item in manifest["artifacts"]:
    path = item["path"].replace("\\", "/")
    committed = blob(BASE, path)
    original = (ORIGINAL / path).read_bytes()
    artifacts.append({
        "path": path,
        "original_matches_manifest": digest(original) == item["sha256"] and len(original) == item["bytes"],
        "git_matches_manifest": digest(committed) == item["sha256"] and len(committed) == item["bytes"],
        "original_lf_equals_git_lf": original.replace(b"\r\n", b"\n") == committed.replace(b"\r\n", b"\n"),
        "original_sha256": digest(original),
        "git_sha256": digest(committed),
    })
copies = []
for name in ("test_independent_model_fields.py", "test_independent_boundary_extra.py"):
    copies.append({"path": name, "copy_sha256": digest((RUN / name).read_bytes()), "review_sha256": digest((REVIEW / name).read_bytes()), "byte_equal": (RUN / name).read_bytes() == (REVIEW / name).read_bytes()})
summary = {
    "at_shanghai": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
    "base_material_sha": BASE,
    "original_artifact_count": len(artifacts),
    "original_raw_matches": sum(item["original_matches_manifest"] for item in artifacts),
    "original_git_exact_matches": sum(item["git_matches_manifest"] for item in artifacts),
    "original_normalized_matches": sum(item["original_lf_equals_git_lf"] for item in artifacts),
    "manifest_unchanged_from_base": blob(BASE, manifest_path) == (ROOT / manifest_path).read_bytes().replace(b"\r\n", b"\n"),
    "reviewer_copies": copies,
    "original_artifacts": artifacts,
}
(RUN / "evidence_audit.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({key: value for key, value in summary.items() if key != "original_artifacts"}))
for path in sorted(RUN.glob("*.xml")):
    cases = list(ET.parse(path).getroot().iter("testcase"))
    counts = {
        "junit": path.name,
        "collected": len(cases),
        "passed": sum(all(case.find(tag) is None for tag in ("failure", "error", "skipped")) for case in cases),
        "failures": sum(case.find("failure") is not None for case in cases),
        "errors": sum(case.find("error") is not None for case in cases),
        "skipped": sum(case.find("skipped") is not None for case in cases),
    }
    (RUN / (path.stem + "_counts.json")).write_text(json.dumps(counts, indent=2), encoding="utf-8")
    print(json.dumps(counts))
assert summary["original_raw_matches"] == 73
assert summary["original_normalized_matches"] == 73
assert summary["manifest_unchanged_from_base"]
assert all(item["byte_equal"] for item in copies)
