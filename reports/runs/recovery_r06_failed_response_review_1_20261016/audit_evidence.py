"""Check frozen author artifacts against Git blobs and retain working-copy differences."""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
AUTHOR = ROOT / "reports/runs/recovery_r06_failed_response_persistence_20261016"
SHA = "9eb01d7ba843116122a9a2462f3b74a2626cc48c"
manifest = json.loads((AUTHOR / "artifact_manifest.json").read_text(encoding="utf-8"))
rows = []
for relative, expected in manifest["artifacts"].items():
    path = relative.replace("\\", "/")
    blob = subprocess.check_output(["git", "show", SHA + ":" + path], cwd=ROOT)
    working = (ROOT / path).read_bytes()
    rows.append({"path": path, "expected_sha256": expected["sha256"], "blob_sha256": hashlib.sha256(blob).hexdigest(), "blob_size_bytes": len(blob), "blob_matches_manifest": hashlib.sha256(blob).hexdigest() == expected["sha256"] and len(blob) == expected["size_bytes"], "working_sha256": hashlib.sha256(working).hexdigest(), "working_matches_blob": working == blob, "blob_crlf_count": blob.count(b"\r\n"), "working_crlf_count": working.count(b"\r\n")})
result = {"checked_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(), "frozen_sha": SHA, "count": len(rows), "blob_matches": sum(row["blob_matches_manifest"] for row in rows), "working_differences": [row for row in rows if not row["working_matches_blob"]], "artifacts": rows}
(RUN / "author_manifest_audit.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
print(json.dumps({key: result[key] for key in ("count", "blob_matches")}))
print("working_differences=" + str(len(result["working_differences"])))
assert all(row["blob_matches_manifest"] for row in rows)
