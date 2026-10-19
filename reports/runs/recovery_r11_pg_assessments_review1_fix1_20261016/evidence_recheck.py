"""Check fixed raw artifacts, source blobs and the untouched initial independent evidence."""

import hashlib
import json
import subprocess
import time
from pathlib import Path

from review_runner import ROOT, RUN, now, record

CODE = "2ddc8fe2ff3e7becfad3b1774a10407911eacbe6"
MATERIAL = "6b10f2c4ed013f4375d51fc31e1cb317409730ac"
OLD_ROOT = Path("D:/wt/r11-pg-assessments-review1")
OLD_RUN = OLD_ROOT / "reports/runs/recovery_r11_pg_assessments_review1_20261016"
AUTHOR = ROOT / "reports/runs/recovery_r11_pg_assessments_raw_fix1_20261016"


def sha(value):
    return hashlib.sha256(value).hexdigest()


def git(*arguments):
    return subprocess.run(["git", *arguments], cwd=ROOT, capture_output=True, check=True).stdout


def verify_manifest(directory, base):
    manifest = directory / "artifact_manifest.json"
    entries = json.loads(manifest.read_text())
    declared = {row["path"] for row in entries}
    actual = {str(p.relative_to(base)).replace("\\", "/") for p in directory.rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.name not in {"artifact_manifest.json", "delivery_receipt.json"}}
    rows = []
    for entry in entries:
        body = (base / entry["path"]).read_bytes()
        rows.append(dict(path=entry["path"], expected_sha256=entry["sha256"], expected_bytes=entry["bytes"], actual_bytes=len(body), actual_sha256=sha(body), lf_sha256=sha(body.replace(b"\r\n", b"\n")), exact_match=sha(body) == entry["sha256"] and len(body) == entry["bytes"]))
    return dict(manifest_sha256=sha(manifest.read_bytes()), declared_count=len(entries), actual_count=len(actual), missing=sorted(declared-actual), undeclared=sorted(actual-declared), mismatch_count=sum(not row["exact_match"] for row in rows), rows=rows)


started, tick = now(), time.monotonic()
raw = verify_manifest(AUTHOR, ROOT)
original_author = verify_manifest(ROOT / "reports/runs/recovery_r11_pg_assessments_20261016", ROOT)
old_independent = verify_manifest(OLD_RUN, OLD_ROOT)
sources = []
for row in json.loads((AUTHOR / "source_manifest.json").read_text()):
    body = (ROOT / row["path"]).read_bytes()
    blob = git("show", CODE + ":" + row["path"])
    blob_id = git("rev-parse", CODE + ":" + row["path"]).decode().strip()
    sources.append(dict(path=row["path"], raw_sha256=sha(body), lf_sha256=sha(body.replace(b"\r\n", b"\n")), expected_raw_sha256=row["sha256"], portable_match=sha(body) == row["sha256"] or sha(body.replace(b"\r\n", b"\n")) == row["sha256"], actual_blob_sha256=sha(blob), actual_blob_id=blob_id, expected_blob_sha256=row["git_blob_sha256"], expected_blob_id=row["git_blob"], blob_match=sha(blob) == row["git_blob_sha256"] and blob_id == row["git_blob"]))
old_report = OLD_ROOT / "reports/reviews/recovery/G-D-R11-pg-assessments-review-1.md"
probe = RUN / "test_independent_boundaries.py"
proof = dict(checked_at=now(), code_sha=CODE, material_sha=MATERIAL, head=git("rev-parse", "HEAD").decode().strip(), fix_raw=raw, original_author_raw=original_author, original_independent_raw=old_independent, source_count=len(sources), source_mismatch_count=sum(not (row["portable_match"] and row["blob_match"]) for row in sources), sources=sources, original_report_actual_sha256=sha(old_report.read_bytes()), original_report_expected_sha256="f92ba375d415b5af55252f7bcac016e227318fa2ac56dcf911436d10ed2e1643", original_probe_sha256=sha((OLD_RUN / "test_independent_boundaries.py").read_bytes()), copied_probe_sha256=sha(probe.read_bytes()), fix_report_expected_sha256=None, fix_report_actual_sha256=sha((ROOT / "reports/tasks/R11-pg-rules-assessments-raw-fix1.md").read_bytes()), production_0021_files=[str(p.relative_to(ROOT)) for p in (ROOT / "backend/migrations/versions").glob("0021*")])
(RUN / "author_raw_and_source_proof.json").write_text(json.dumps(proof, ensure_ascii=False, indent=2), encoding="utf-8")
(RUN / "author_artifact_manifest.exact.json").write_bytes((AUTHOR / "artifact_manifest.json").read_bytes())
(RUN / "author_source_manifest.exact.json").write_bytes((AUTHOR / "source_manifest.json").read_bytes())
assert all(item["mismatch_count"] == 0 and not item["missing"] and not item["undeclared"] for item in (raw, original_author, old_independent))
assert proof["source_mismatch_count"] == 0
assert proof["original_report_actual_sha256"] == proof["original_report_expected_sha256"]
assert proof["original_probe_sha256"] == proof["copied_probe_sha256"]
record("evidence_recheck", ["evidence_recheck.py", "55+118+80 actual raw; 7 source blobs"], ROOT, started, time.monotonic()-tick, 0)
print(json.dumps(dict(fix_raw=raw["declared_count"], old_author=original_author["declared_count"], old_independent=old_independent["declared_count"], source_count=len(sources), source_mismatch=proof["source_mismatch_count"], initial_report_unchanged=True)))
