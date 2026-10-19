"""Copy only this review's report and immutable raw evidence to the controller tree."""

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
MAIN = Path("D:/dianzi")
REPORT_PATH = Path("reports/reviews/recovery/G-C-R06-catalog-combined-review-1.md")
RUN_PATH = Path("reports/runs/recovery_r06_catalog_combined_review_1_20261015")
started = datetime.now(timezone(timedelta(hours=8))).isoformat()
target_run = MAIN / RUN_PATH
target_report = MAIN / REPORT_PATH
assert not target_report.exists()
assert not target_run.exists()
target_report.parent.mkdir(parents=True, exist_ok=True)
target_run.mkdir()
report_bytes = (ROOT / REPORT_PATH).read_bytes()
target_report.write_bytes(report_bytes)
raw = {path.name: path.read_bytes() for path in RUN.iterdir() if path.is_file()}
for name, content in raw.items():
    (target_run / name).write_bytes(content)
    assert (target_run / name).read_bytes() == content
assert target_report.read_bytes() == report_bytes
ended = datetime.now(timezone(timedelta(hours=8))).isoformat()
metadata = {
    "started_at": started, "ended_at": ended, "exit_code": 0,
    "argv": [str(ROOT / "backend/.venv/Scripts/python.exe"), str(Path(__file__).resolve())],
    "cwd": str(ROOT / "backend"),
    "copied_report": str(target_report),
    "report_sha256": hashlib.sha256(report_bytes).hexdigest(),
    "copied_run": str(target_run), "copied_raw_file_count": len(raw),
    "files_sha256": {name: hashlib.sha256(content).hexdigest() for name, content in raw.items()},
    "temp_cache_directories_copied": False,
}
encoded = json.dumps(metadata, ensure_ascii=False, indent=2).encode()
(RUN / "handoff_copy.json").write_bytes(encoded)
(target_run / "handoff_copy.json").write_bytes(encoded)
print(json.dumps({key: value for key, value in metadata.items() if key != "files_sha256"}, ensure_ascii=False, indent=2))
