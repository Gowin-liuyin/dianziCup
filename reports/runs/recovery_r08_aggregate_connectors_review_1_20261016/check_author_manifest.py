"""Verify Git blob bytes separately from Windows checkout line endings."""

import hashlib
import json
from pathlib import Path
import subprocess

WORKTREE = Path(__file__).resolve().parents[3]
HEAD = "82a85b08eea39acd10b4ebf6a2966f5e39108799"
CODE = "8e150878a76e541e377b300f851d9c7caf919019"
MANIFEST_PATH = "reports/runs/recovery_r08_aggregate_connectors_20261016/artifact_manifest.json"


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def main() -> int:
    manifest = json.loads(subprocess.check_output(["git", "show", f"{HEAD}:{MANIFEST_PATH}"], cwd=WORKTREE))
    entries = []
    for group, sha in (("source_blobs", CODE), ("artifacts", HEAD)):
        for expected in manifest[group]:
            path = expected["path"]
            blob = subprocess.check_output(["git", "show", f"{sha}:{path}"], cwd=WORKTREE)
            checkout = (WORKTREE / path).read_bytes()
            entries.append({
                "group": group,
                "path": path,
                "blob_sha": sha,
                "expected_size_bytes": expected["size_bytes"],
                "blob_size_bytes": len(blob),
                "blob_sha256": digest(blob),
                "blob_matches_manifest": len(blob) == expected["size_bytes"] and digest(blob) == expected["sha256"],
                "checkout_size_bytes": len(checkout),
                "checkout_sha256": digest(checkout),
                "checkout_equals_blob": checkout == blob,
                "checkout_lf_normalized_equals_blob": checkout.replace(b"\r\n", b"\n") == blob,
            })
    failures = [entry["path"] for entry in entries if not entry["blob_matches_manifest"]]
    receipt = {
        "head_sha": HEAD,
        "code_sha": CODE,
        "total_entries": len(entries),
        "source_count": len(manifest["source_blobs"]),
        "artifact_count": len(manifest["artifacts"]),
        "git_blob_failures": failures,
        "checkout_differences": [entry["path"] for entry in entries if not entry["checkout_equals_blob"]],
        "entries": entries,
    }
    Path(__file__).with_name("author_manifest_validation.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in receipt.items() if key != "entries"}, ensure_ascii=False))
    return bool(failures)


if __name__ == "__main__":
    raise SystemExit(main())
