"""Freeze the minimal shared helper and dedicated tests without modifying the prior 518 or evidence."""

import hashlib
import json
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
BASE = "7a653880af12e4160ca8edf26fccbaf5d1e6f0f0"
FILES = ["frontend/src/features/assets/asset-contracts.ts", "frontend/src/features/assets/sbom-purl-fix1.test.ts", "frontend/tests/r17_purl_profile_cases.ts"]


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT)


if git("rev-parse", "HEAD").decode().strip() != BASE or git("diff", "--cached", "--name-only"):
    raise RuntimeError("unexpected branch or staged content")
rows = []
for name in git("ls-tree", "-r", "--name-only", BASE, "frontend").decode().splitlines():
    if name.endswith((".test.ts", ".test.tsx", ".spec.ts")):
        frozen = git("show", BASE + ":" + name)
        current = (ROOT / name).read_bytes()
        if frozen.replace(b"\r\n", b"\n") != current.replace(b"\r\n", b"\n"):
            raise RuntimeError("existing original test changed")
        rows.append({"path": name, "git_lf_sha256": hashlib.sha256(frozen).hexdigest(), "worktree_raw_sha256": hashlib.sha256(current).hexdigest(), "lf_equal": True})
(RUN / "original_518_source_proof.json").write_text(json.dumps({"baseline_sha": BASE, "files": rows, "mismatches": 0}, indent=2) + "\n", encoding="utf-8", newline="\n")
git("add", "--", *FILES)
if set(git("diff", "--cached", "--name-only").decode().splitlines()) != set(FILES):
    raise RuntimeError("source staging exceeds ownership")
git("diff", "--cached", "--check")
(RUN / "source_change.diff").write_bytes(git("diff", "--cached", "--no-ext-diff"))
git("commit", "-m", "G-E R17 fix raw PURL version segmentation across snapshot and sidecar display")
source = git("rev-parse", "HEAD").decode().strip()
receipt = {"baseline_sha": BASE, "source_sha": source, "frozen_at": datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds"), "source_files": FILES, "existing_test_spec_lf_unchanged": len(rows), "status": "awaiting_review"}
(RUN / "source_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps(receipt))
