"""Write hashes for this diagnostic's owned artifacts only."""

import hashlib
import json
from pathlib import Path


OUTPUT = Path(__file__).resolve().parent
ROOT = OUTPUT.parents[2]
report = ROOT / "reports/reviews/recovery/G-C-native-cpu-limit-diagnosis.md"
paths = [path for path in OUTPUT.rglob("*") if path.is_file() and path.name != "artifact_hashes.json"] + [report]
manifest = [{"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for path in sorted(paths)]
(OUTPUT / "artifact_hashes.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
print(json.dumps({"artifact_files": len(manifest), "report_sha256": hashlib.sha256(report.read_bytes()).hexdigest(), "manifest_sha256": hashlib.sha256((OUTPUT / "artifact_hashes.json").read_bytes()).hexdigest()}))
