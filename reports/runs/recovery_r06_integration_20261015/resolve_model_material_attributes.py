"""Preserve both disjoint run-specific raw-byte rules in a material-only conflict."""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
path = ROOT / ".gitattributes"
unmerged = subprocess.check_output(["git", "diff", "--name-only", "--diff-filter=U"], cwd=ROOT, text=True).splitlines()
assert unmerged == [".gitattributes"], unmerged
before = path.read_bytes()
lines = before.decode("utf-8").splitlines(keepends=True)
starts = [i for i, line in enumerate(lines) if line.startswith("<<<<<<< ")]
middles = [i for i, line in enumerate(lines) if line.startswith("=======")]
ends = [i for i, line in enumerate(lines) if line.startswith(">>>>>>> ")]
assert len(starts) == len(middles) == len(ends) == 1
start, middle, end = starts[0], middles[0], ends[0]
assert start < middle < end
ours, theirs = lines[start + 1:middle], lines[middle + 1:end]
assert all(
    not line.strip()
    or line.startswith("reports/runs/")
    or line.strip() == "reports/tasks/R07-model-fields-two-root-causes-fix.md -text"
    for line in ours + theirs
)
merged = "".join(lines[:start] + ours + theirs + lines[end + 1:]).encode()
assert b"<<<<<<<" not in merged and b">>>>>>>" not in merged
path.write_bytes(merged)
subprocess.run(["git", "add", "--", ".gitattributes"], cwd=ROOT, check=True)
argv = ["git", "commit", "--no-edit"]
with (RUN / "model_material_conflict_commit.log").open("xb") as output:
    result = subprocess.run(argv, cwd=ROOT, stdout=output, stderr=subprocess.STDOUT, timeout=60)
receipt = {"recorded_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
    "unmerged_before": unmerged, "source_changes_in_conflict": 0,
    "resolution": "both disjoint run-specific raw-byte rules retained, no source/test semantic conflict",
    "before_sha256": hashlib.sha256(before).hexdigest(), "after_sha256": hashlib.sha256(merged).hexdigest(),
    "ours_lines": len(ours), "theirs_lines": len(theirs), "argv": argv, "exit_code": result.returncode,
    "head_after": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
    "push_attempts": 0}
(RUN / "model_material_conflict_resolution_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"exit_code": result.returncode, "head_after": receipt["head_after"]}))
raise SystemExit(result.returncode)
