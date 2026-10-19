"""Freeze the independent targeted recheck and exact artifact hashes."""

from datetime import datetime
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
OUTPUT = Path(__file__).resolve().parent
REPORT = ROOT / "reports/reviews/recovery/G-C-native-cpu-guard-review-1-recheck.md"
paths = [path for path in OUTPUT.rglob("*") if path.is_file()
         and path.name != "artifact_manifest.json"] + [REPORT]
entries = [{"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for path in sorted(paths)]
manifest = {
    "review_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
    "code_sha": "852472810b20b113606a0275ae6861326d39ebe8",
    "fix_merge_base": "994c381edd2c4f0743d9c76f83abefaf51359f14",
    "original_merge_base": "45ee2d0d3bb007f0dbf5d753ee4b8c06d322758b",
    "recorded_checks_started_at": "2026-10-15T21:55:30.238889+08:00",
    "recorded_checks_completed_at": "2026-10-15T22:03:32.880636+08:00",
    "frozen_at": datetime.now().astimezone().isoformat(),
    "verdict": "Ship; original Must 1 closed; native CPU guard scope only",
    "artifact_count_excluding_manifest": len(entries),
    "artifacts": entries,
}
destination = OUTPUT / "artifact_manifest.json"
destination.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
print(json.dumps({"report_sha256": hashlib.sha256(REPORT.read_bytes()).hexdigest(),
                  "manifest_sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
                  "artifacts_excluding_manifest": len(entries), "frozen_at": manifest["frozen_at"]}))
