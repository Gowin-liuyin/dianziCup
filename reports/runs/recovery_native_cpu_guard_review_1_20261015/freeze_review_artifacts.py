"""Freeze the independent review report and evidence without a self-referential hash."""

from datetime import datetime
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
OUTPUT = Path(__file__).resolve().parent
REPORT = ROOT / "reports/reviews/recovery/G-C-native-cpu-guard-review-1.md"
paths = [path for path in OUTPUT.rglob("*") if path.is_file()
         and path.name != "artifact_manifest.json"] + [REPORT]
entries = [{"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for path in sorted(paths)]
manifest = {
    "review_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
    "code_sha": "36884c7860434314174adac92dda1947f4469a81",
    "merge_base": "45ee2d0d3bb007f0dbf5d753ee4b8c06d322758b",
    "recorded_checks_started_at": "2026-10-15T21:17:25.760281+08:00",
    "recorded_checks_completed_at": "2026-10-15T21:25:32.801156+08:00",
    "frozen_at": datetime.now().astimezone().isoformat(),
    "verdict": "Must fix 1 first; native CPU guard scope only",
    "artifact_count_excluding_manifest": len(entries),
    "artifacts": entries,
}
destination = OUTPUT / "artifact_manifest.json"
destination.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
print(json.dumps({"report_sha256": hashlib.sha256(REPORT.read_bytes()).hexdigest(),
                  "manifest_sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
                  "artifacts_excluding_manifest": len(entries), "frozen_at": manifest["frozen_at"]}))
