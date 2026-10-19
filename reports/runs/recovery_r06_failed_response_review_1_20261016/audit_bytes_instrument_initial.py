"""Verify all 87 tracked author run files against their original, unnormalized bytes."""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
ORIGINAL = Path("D:/wt/r06-failed-response-persistence")
SHA = "9eb01d7ba843116122a9a2462f3b74a2626cc48c"
PREFIX = "reports/runs/recovery_r06_failed_response_persistence_20261016"
paths = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", SHA, "--", PREFIX], cwd=ROOT, text=True).splitlines()
rows = []
for path in paths:
    blob = subprocess.check_output(["git", "show", SHA + ":" + path], cwd=ROOT)
    original = (ORIGINAL / path).read_bytes()
    working = (ROOT / path).read_bytes()
    rows.append({"path": path, "size_bytes": len(original), "original_sha256": hashlib.sha256(original).hexdigest(), "git_blob_sha256": hashlib.sha256(blob).hexdigest(), "original_matches_git_blob": original == blob, "review_checkout_matches_git_blob": working == blob, "original_crlf_count": original.count(b"\r\n"), "review_checkout_crlf_count": working.count(b"\r\n")})
result = {"checked_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(), "frozen_sha": SHA, "original_path": str(ORIGINAL), "tracked_count": len(rows), "original_matches": sum(row["original_matches_git_blob"] for row in rows), "review_checkout_differences": [row for row in rows if not row["review_checkout_matches_git_blob"]], "artifacts": rows}
(RUN / "original_bytes_audit.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
print(json.dumps({key: result[key] for key in ("tracked_count", "original_matches")}))
assert len(rows) == 87 and all(row["original_matches_git_blob"] for row in rows)
