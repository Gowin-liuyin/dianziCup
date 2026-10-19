"""Use current reviewed blobs for source-only ancestry after retaining the failed merge-base patch."""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
SOURCE = "c691a0d5d0e06a4cc52567e1e816cd49cb0b1e7f"
BEFORE = "8514ebb16fedfe026cc280b78fced993af1dc5e8"


def git(*arguments):
    return subprocess.check_output(["git", *arguments], cwd=ROOT, timeout=120)


assert git("rev-parse", "HEAD").decode().strip() == BEFORE
assert not git("diff", "--cached", "--name-only").strip()
changed = git("diff", "--name-only", BEFORE, SOURCE, "--", "sdk/python").decode().splitlines()
assert len(changed) == 7
previous = json.loads((RUN / "source_integration_batch2_receipt.json").read_text())
all_paths = previous["packages"][-1]["files"]
unchanged = set(all_paths) - set(changed)
assert len(unchanged) == 10
assert all(git("show", BEFORE + ":" + path) == git("show", SOURCE + ":" + path) for path in unchanged)
patch = git("diff", "--binary", BEFORE, SOURCE, "--", *changed)
(RUN / "batch2_mcp_current_reviewed_blobs.patch").write_bytes(patch)
with (RUN / "batch2_mcp_current_reviewed_blobs_apply.log").open("xb") as output:
    applied = subprocess.run(["git", "apply", "--index", "--binary", "-"], input=patch, cwd=ROOT, stdout=output, stderr=subprocess.STDOUT, timeout=120, check=False)
assert applied.returncode == 0
assert set(git("diff", "--cached", "--name-only").decode().splitlines()) == set(changed)
assert all(git("show", ":" + path) == git("show", SOURCE + ":" + path) for path in changed)
assert subprocess.run(["git", "diff", "--cached", "--check"], cwd=ROOT, check=False).returncode == 0
assert subprocess.run(["git", "-c", "gc.auto=0", "commit", "-m", "Recovery checkpoint integrate reviewed MCP output budget and safe error boundary"], cwd=ROOT, check=False).returncode == 0
head = git("rev-parse", "HEAD").decode().strip()
(RUN / "mcp_batch2_recovery_receipt.json").write_text(json.dumps({"recorded_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"), "before": BEFORE, "reviewed_source": SOURCE, "head": head, "changed": changed, "previously_integrated_blobs_unchanged": sorted(unchanged), "patch_sha256": hashlib.sha256(patch).hexdigest(), "failed_merge_base_patch_preserved": True, "stage_accepted": False, "push": "not_run"}, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps({"integrated_sha": head, "new_files": len(changed), "previous_reviewed_files_unchanged": len(unchanged)}))
