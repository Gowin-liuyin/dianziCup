"""Commit only the authorized owned review ranges after staged boundary checks."""

import gzip
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
REPORT = "reports/reviews/recovery/G-D-R12-projection-failure-budget-review-1.md"
PREFIX = RUN.relative_to(ROOT).as_posix() + "/"


def git(*arguments):
    result = subprocess.run(["git", *arguments], cwd=ROOT, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    return result.stdout


for name in ("stage_delivery.stdout.log", "stage_delivery.stderr.log", "delivery_staged_diff.raw.log"):
    path = RUN / name
    packed = path.with_name(name + ".gz")
    assert not packed.exists()
    packed.write_bytes(gzip.compress(path.read_bytes(), mtime=0))
    assert gzip.decompress(packed.read_bytes()) == path.read_bytes()
extra = [
    RUN / "stage_delivery.command.json",
    RUN / "delivery_staged_summary.json",
    RUN / "stage_delivery.stdout.log.gz",
    RUN / "stage_delivery.stderr.log.gz",
    RUN / "delivery_staged_diff.raw.log.gz",
    Path(__file__),
]
git("add", "--", *(path.relative_to(ROOT).as_posix() for path in extra))
actual = git("diff", "--cached", "--name-only").decode().splitlines()
assert actual
assert all(name == REPORT or name.startswith(PREFIX) for name in actual)
assert not any("/mypy_cache/" in name or "_tmp/" in name for name in actual)
git("diff", "--cached", "--check")
git("-c", "gc.auto=0", "commit", "-m", "docs: record independent R12 projection failure budget review")
review_sha = git("rev-parse", "HEAD").decode().strip()
changed = git("diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD").decode().splitlines()
assert set(changed) == set(actual)
assert not git("diff", "HEAD^", "HEAD", "--", "backend", "docs", "progress")
record = {
    "review_sha": review_sha,
    "source_parent": git("rev-parse", "HEAD^").decode().strip(),
    "committed_paths": changed,
    "committed_count": len(changed), "outside_owned_scope": [],
    "staged_diff_check_exit_code": 0, "backend_docs_progress_changed": False,
    "push_performed": False,
}
(RUN / "review_commit_receipt.json").write_text(json.dumps(record, indent=2) + "\n")
print(json.dumps({"review_sha": review_sha, "paths": len(changed), "push": False}))
