"""Check author metadata against the fixed Git blobs rather than current author paths."""

from __future__ import annotations

import datetime
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
FROZEN = "535c0a537bc24cb52c64511c72eeb4ea3ae5bc34"
MANIFEST = "reports/runs/r20_process_startup_fix_20261016/artifact_manifest.json"


def git_bytes(*argv: str) -> bytes:
    return subprocess.run(["git", *argv], cwd=ROOT, capture_output=True, check=True).stdout


def main() -> None:
    raw = git_bytes("show", f"{FROZEN}:{MANIFEST}")
    manifest = json.loads(raw)
    artifacts = manifest["artifacts"]
    failures = []
    receipts = []
    for artifact in artifacts:
        path = artifact["relative_path"]
        blob_id = git_bytes("rev-parse", f"{FROZEN}:{path}").decode().strip()
        content = git_bytes("show", f"{FROZEN}:{path}")
        if blob_id != artifact["git_blob"] or hashlib.sha256(content).hexdigest() != artifact["sha256_lf"]:
            failures.append(path)
        if path.endswith(".json"):
            item = json.loads(content)
            if "argv" in item and "exit_code" in item:
                receipts.append({"path": path, "exit_code": item["exit_code"], "cwd": item.get("cwd"), "argv": item["argv"]})
    expected_manifest = "d2520b0aef5fe79cec500de60c662e3e4aafe98324fcf0293e6f316bac85ec47"
    result = {"frozen_sha": FROZEN, "manifest_sha256_git_blob": hashlib.sha256(raw).hexdigest(), "expected_manifest_sha256": expected_manifest, "artifact_count": len(artifacts), "receipt_count": len(receipts), "mismatches": failures, "receipts": receipts, "checked_shanghai": datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(timespec="seconds")}
    (RUN / "frozen_metadata_audit.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    assert len(artifacts) == 85 and len(receipts) == 29 and not failures
    assert result["manifest_sha256_git_blob"] == expected_manifest
    print(json.dumps({key: value for key, value in result.items() if key != "receipts"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
