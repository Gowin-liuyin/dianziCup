"""Verify author raw declarations and frozen Git blobs, retaining the old mismatch ledger."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
OLD = "bae3138d103427d659d7fdc0a8a195088dd42f2e"
MANIFEST = "reports/runs/recovery_r06_live_restart_preparation_20261016/artifact_manifest.json"


def blob(sha: str, path: str) -> bytes:
    return subprocess.check_output(["git", "show", sha + ":" + path], cwd=ROOT)


def audit(sha: str, checkout: bool):
    raw_manifest = blob(sha, MANIFEST)
    manifest = json.loads(raw_manifest)
    rows = []
    for relative, declared in manifest["files"].items():
        path = Path(relative).as_posix()
        frozen = blob(sha, path)
        raw = (ROOT / relative).read_bytes() if checkout else frozen
        rows.append({"path": path, "declared_sha256": declared["sha256"],
                     "raw_sha256": hashlib.sha256(raw).hexdigest(), "git_blob_sha256": hashlib.sha256(frozen).hexdigest(),
                     "raw_bytes": len(raw), "declared_bytes": declared["bytes"],
                     "manifest_raw_match": hashlib.sha256(raw).hexdigest() == declared["sha256"] and len(raw) == declared["bytes"],
                     "raw_git_match": raw == frozen})
    return {"tool_sha": sha, "manifest_sha256": hashlib.sha256(raw_manifest).hexdigest(),
            "checkout_compared": checkout, "entry_count": len(rows),
            "manifest_raw_mismatch_count": sum(not row["manifest_raw_match"] for row in rows),
            "raw_git_mismatch_count": sum(not row["raw_git_match"] for row in rows), "files": rows}


def main():
    current = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    result = {"old_bae": audit(OLD, False), "current": audit(current, True)}
    destination = RUN / ("material_audit_" + sys.argv[1] + ".json")
    destination.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: {field: value[field] for field in ("tool_sha", "manifest_sha256", "entry_count", "manifest_raw_mismatch_count", "raw_git_mismatch_count")}
                      for key, value in result.items()}))


if __name__ == "__main__":
    main()
