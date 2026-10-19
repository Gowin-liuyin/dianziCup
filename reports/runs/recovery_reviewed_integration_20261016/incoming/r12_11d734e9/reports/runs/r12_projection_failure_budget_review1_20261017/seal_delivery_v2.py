"""Seal stable final review files and preserve every preceding raw evidence version."""

import gzip
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
REPORT = ROOT / "reports/reviews/recovery/G-D-R12-projection-failure-budget-review-1.md"
ACTIVE_PREFIXES = ("seal.", "seal_fixed.", "delivery_seal.", "delivery_seal_v2.")
source = json.loads((RUN / "source_manifest.json").read_text())
for item in source["inputs"]:
    assert hashlib.sha256((ROOT / item["path"]).read_bytes()).hexdigest() == item["raw_sha256"]
archives = []
for path in sorted(RUN.iterdir()):
    if not path.is_file() or path.name.startswith(ACTIVE_PREFIXES):
        continue
    if path.name.endswith((".log", ".xml", ".patch")):
        raw = path.read_bytes()
        archive = path.with_name(path.name + ".gz")
        if not archive.exists():
            archive.write_bytes(gzip.compress(raw, mtime=0))
        assert gzip.decompress(archive.read_bytes()) == raw
        archives.append({
            "path": path.name, "raw_sha256": hashlib.sha256(raw).hexdigest(),
            "bytes": len(raw), "archive": archive.name,
            "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        })
files = []
for path in sorted(RUN.iterdir()):
    if not path.is_file() or path.name.startswith(ACTIVE_PREFIXES):
        continue
    raw = path.read_bytes()
    files.append({
        "path": path.name, "bytes": len(raw), "raw_sha256": hashlib.sha256(raw).hexdigest(),
    })
record = {
    "sealed_at": datetime.now(UTC).isoformat(), "source": source["source"],
    "baseline": source["baseline"], "author_material": "7813bbf27e31e66d5f53cd595a0278d962092a39",
    "report_path": REPORT.relative_to(ROOT).as_posix(),
    "report_raw_sha256": hashlib.sha256(REPORT.read_bytes()).hexdigest(),
    "files": files, "raw_archives": archives,
    "raw_evidence_deleted_or_modified": False,
    "active_output_excluded": ACTIVE_PREFIXES,
    "earlier_manifests_are_historical_not_current_snapshot": True,
}
path = RUN / "review_delivery_manifest_v2.json"
assert not path.exists()
path.write_text(json.dumps(record, indent=2) + "\n")
print(json.dumps({"report_sha256": record["report_raw_sha256"], "files": len(files), "archives": len(archives)}))
