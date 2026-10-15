"""Export only tracked frontend and quality inputs from immutable Git objects."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess


RUN_ROOT = Path(__file__).resolve().parent
CANDIDATE_ROOT = Path("C:/Users/yinha/.codex/worktrees/recovery-r01-vitest-candidate/dianzi")
CANDIDATE_SHA = "497740a771e7cb2d719ab22ebad34bd30539e20d"
BASELINE_SHA = "d0a179eeb3621cdf21a4cba94a6b5bd4e8a2a120"
QUALITY_SHA = "4a17ca7b967a10d6077ba5219984a2d1a74cf320"


def git_bytes(*arguments: str) -> bytes:
    return subprocess.check_output(["git", *arguments], cwd=CANDIDATE_ROOT)


def export_frontend(sha: str, name: str) -> dict[str, str]:
    destination = RUN_ROOT / name
    if destination.exists():
        raise ValueError("Review exports must be fresh")
    paths = git_bytes("ls-tree", "-r", "--name-only", sha, "--", "frontend").decode().splitlines()
    hashes: dict[str, str] = {}
    for path in paths:
        if any(part in {".env", "KEYS", "holdout"} for part in Path(path).parts):
            raise ValueError("Protected input in frontend export")
        contents = git_bytes("show", f"{sha}:{path}")
        output = destination / path
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(contents)
        hashes[path] = hashlib.sha256(contents).hexdigest()
    return hashes


def main() -> None:
    assert git_bytes("rev-parse", "HEAD").decode().strip() == CANDIDATE_SHA
    assert not git_bytes("status", "--porcelain").strip()
    candidate_hashes = export_frontend(CANDIDATE_SHA, "candidate_replay")
    baseline_hashes = export_frontend(BASELINE_SHA, "baseline_replay")
    quality_bytes = git_bytes("show", f"{QUALITY_SHA}:scripts/dev.py")
    quality_path = RUN_ROOT / "candidate_replay" / "scripts" / "dev.py"
    quality_path.parent.mkdir(parents=True, exist_ok=True)
    quality_path.write_bytes(quality_bytes)
    metadata = {
        "candidate_sha": CANDIDATE_SHA,
        "candidate_tree": git_bytes("rev-parse", f"{CANDIDATE_SHA}^{{tree}}").decode().strip(),
        "baseline_sha": BASELINE_SHA,
        "baseline_tree": git_bytes("rev-parse", f"{BASELINE_SHA}^{{tree}}").decode().strip(),
        "candidate_hashes": candidate_hashes,
        "baseline_hashes": baseline_hashes,
        "changed_frontend_paths": sorted(path for path in candidate_hashes if candidate_hashes[path] != baseline_hashes[path]),
        "quality_sha": QUALITY_SHA,
        "quality_blob": git_bytes("rev-parse", f"{QUALITY_SHA}:scripts/dev.py").decode().strip(),
        "quality_sha256": hashlib.sha256(quality_bytes).hexdigest(),
    }
    (RUN_ROOT / "inputs.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (RUN_ROOT / "frozen_diff.patch").write_bytes(git_bytes("diff", BASELINE_SHA, CANDIDATE_SHA, "--", "frontend", ".gitattributes"))
    (RUN_ROOT / "frozen_paths.txt").write_bytes(git_bytes("diff", "--name-status", BASELINE_SHA, CANDIDATE_SHA))
    (RUN_ROOT / "candidate_before.status.txt").write_bytes(git_bytes("status", "--porcelain"))
    print(json.dumps({key: value for key, value in metadata.items() if not key.endswith("hashes")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
