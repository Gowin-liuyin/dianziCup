"""Freeze exact and LF-normalized hashes of owned evidence for an independent checkout."""

from datetime import datetime
import hashlib
import json
from pathlib import Path

OUTPUT = Path(__file__).resolve().parent
ROOT = OUTPUT.parents[2]
paths = sorted(path for path in OUTPUT.iterdir() if path.is_file() and path.name != "artifact_hashes.json")
paths.append(ROOT / "reports/tasks/R20-native-cpu-guard.md")
manifest = {
    "generated_at": datetime.now().astimezone().isoformat(),
    "code_sha": "852472810b20b113606a0275ae6861326d39ebe8",
    "base_sha": "994c381edd2c4f0743d9c76f83abefaf51359f14",
    "files": {},
}
for path in paths:
    content = path.read_bytes()
    manifest["files"][str(path.relative_to(ROOT)).replace("\\", "/")] = {
        "sha256": hashlib.sha256(content).hexdigest(),
        "lf_sha256": hashlib.sha256(content.replace(b"\r\n", b"\n")).hexdigest(),
        "bytes": len(content),
    }
(OUTPUT / "artifact_hashes.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
print(json.dumps({"file_count": len(paths), "manifest_sha256": hashlib.sha256(
    (OUTPUT / "artifact_hashes.json").read_bytes()).hexdigest(),
    "report_sha256": manifest["files"]["reports/tasks/R20-native-cpu-guard.md"]["sha256"]}))
