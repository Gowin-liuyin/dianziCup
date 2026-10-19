"""Seal exact review evidence while leaving all earlier raw files in place."""

import gzip
import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
REPORT = ROOT / "reports/reviews/recovery/G-D-R12-projection-failure-budget-review-1.md"
manifest = json.loads((RUN / "source_manifest.json").read_text())
for item in manifest["inputs"]:
    assert hashlib.sha256((ROOT / item["path"]).read_bytes()).hexdigest() == item["raw_sha256"]
raw_archives = []
for path in sorted(RUN.iterdir()):
    if path.name.startswith(("seal.", "seal_fixed.")):
        continue
    if path.name.endswith((".log", ".xml")):
        archive = path.with_name(path.name + ".gz")
        raw = path.read_bytes()
        packed = gzip.compress(raw, mtime=0)
        if archive.exists():
            assert gzip.decompress(archive.read_bytes()) == raw
        else:
            archive.write_bytes(packed)
        assert gzip.decompress(packed) == raw
        raw_archives.append({
            "path": path.name, "bytes": len(raw),
            "raw_sha256": hashlib.sha256(raw).hexdigest(),
            "archive": archive.name,
            "archive_sha256": hashlib.sha256(packed).hexdigest(),
        })
files = []
for path in sorted(RUN.iterdir()):
    if path.name.startswith(("seal.", "seal_fixed.")):
        continue
    if path.is_file():
        raw = path.read_bytes()
        files.append({"path": path.name, "bytes": len(raw), "raw_sha256": hashlib.sha256(raw).hexdigest()})
source_diff = subprocess.check_output(
    ["git", "diff", "--name-only", manifest["source"], "--", "backend"], cwd=ROOT, timeout=10
).decode().splitlines()
assert not source_diff
report_raw = REPORT.read_bytes()
result = {
    "sealed_at": datetime.now(UTC).isoformat(),
    "baseline": manifest["baseline"], "source": manifest["source"],
    "author_material": "7813bbf27e31e66d5f53cd595a0278d962092a39",
    "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, timeout=10).decode().strip(),
    "report_path": REPORT.relative_to(ROOT).as_posix(),
    "report_raw_sha256": hashlib.sha256(report_raw).hexdigest(),
    "report_bytes": len(report_raw),
    "report_created_at_from_filesystem": datetime.fromtimestamp(REPORT.stat().st_ctime, UTC).isoformat(),
    "report_modified_at_from_filesystem": datetime.fromtimestamp(REPORT.stat().st_mtime, UTC).isoformat(),
    "business_source_unchanged_after_review": not source_diff,
    "raw_archives": raw_archives, "files": files,
    "harness_note": "final instrument snapshot; CBM/terminal support was added after earlier offline runs",
    "earlier_raw_evidence_deleted_or_modified": False,
    "supersedes": "review_evidence_manifest.json; first seal included its active stdout before the final print",
    "paid_calls": 0, "cost": "unknown", "service_credentials_loaded": False,
}
path = RUN / "review_evidence_manifest_fixed.json"
assert not path.exists()
path.write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps({"report_raw_sha256": result["report_raw_sha256"], "files": len(files), "archives": len(raw_archives)}))
