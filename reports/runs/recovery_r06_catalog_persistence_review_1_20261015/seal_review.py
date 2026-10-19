"""Seal only this review's artifacts and copy them to the controller workspace."""

import hashlib
import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
REPORT = ROOT / "reports/reviews/recovery/G-C-R06-catalog-persistence-review-1.md"
CONTROLLER = Path("D:/dianzi")
assert RUN.is_relative_to(ROOT / "reports/runs/recovery_r06_catalog_persistence_review_1_20261015")
assert REPORT.name == "G-C-R06-catalog-persistence-review-1.md"
files = [path for path in sorted(RUN.rglob("*")) if path.is_file()
         and "__pycache__" not in path.parts and path.suffix != ".pyc"
         and path.name not in {"artifact_hashes.json", "copy_receipt.json"}]
manifest = {
    "sealed_at": datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds"),
    "fixed_sha": "45ee2d0d3bb007f0dbf5d753ee4b8c06d322758b",
    "fixed_tree": "82e588b929f91de2c12df22690da55c3db04bbda",
    "scope": "four fixes behavior recheck only; whole slice awaits new independent combination review",
    "review_report": REPORT.relative_to(ROOT).as_posix(),
    "review_report_sha256": hashlib.sha256(REPORT.read_bytes()).hexdigest(),
    "files": [{"path": path.relative_to(RUN).as_posix(), "bytes": path.stat().st_size,
               "sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for path in files],
}
manifest_path = RUN / "artifact_hashes.json"
manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
for source in [REPORT, *files, manifest_path]:
    target = CONTROLLER / source.relative_to(ROOT)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    assert hashlib.sha256(target.read_bytes()).digest() == hashlib.sha256(source.read_bytes()).digest()
receipt = {"report": str(CONTROLLER / REPORT.relative_to(ROOT)),
           "report_sha256": manifest["review_report_sha256"],
           "run": str(CONTROLLER / RUN.relative_to(ROOT)),
           "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
           "copied_run_files": len(files) + 1,
           "business_files_written": 0,
           "shared_public_cleanup": False}
(RUN / "copy_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
shutil.copyfile(RUN / "copy_receipt.json", CONTROLLER / RUN.relative_to(ROOT) / "copy_receipt.json")
print(json.dumps(receipt))
