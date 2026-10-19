"""Keep exact evidence rules when Git synthesizes conflict markers in a virtual merge base."""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent


def git(*arguments):
    return subprocess.check_output(["git", *arguments], cwd=ROOT, text=True, encoding="utf-8").strip()


def now():
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


assert git("rev-parse", "HEAD") == "691b7978af9e885e9bb5c8195ab07518629ef6c4"
assert git("rev-parse", "MERGE_HEAD") == "bc8798cf5efc81e210a429884930ca545af43ad8"
assert git("diff", "--name-only", "--diff-filter=U") == ".gitattributes"
base, ours, theirs = [git("show", f":{stage}:.gitattributes").splitlines() for stage in (1, 2, 3)]
markers = {"<<<<<<<<< Temporary merge branch 1", "=========", ">>>>>>>>> Temporary merge branch 2"}
assert (set(base) - set(ours)) <= markers and (set(base) - set(theirs)) <= markers
additions = [line for line in theirs if line not in ours]
assert all(not line or line.startswith("reports/") for line in additions)
(ROOT / ".gitattributes").write_text("\n".join(ours + additions) + "\n", encoding="utf-8")
subprocess.run(["git", "add", "--", ".gitattributes"], cwd=ROOT, check=True)
with (RUN / "asset-inventory-persistence_virtual_base_resolution.log").open("xb") as output:
    subprocess.run(["git", "diff", "--cached", "--check"], cwd=ROOT, stdout=output, stderr=subprocess.STDOUT, check=True)
    subprocess.run(["git", "commit", "-m", "G-D integrate reviewed private asset inventory and immutable history"], cwd=ROOT, stdout=output, stderr=subprocess.STDOUT, check=True)
path = RUN / "persistent_slices_integration_receipt.json"
receipt = json.loads(path.read_text(encoding="utf-8"))
item = receipt["packages"][-1]
assert item["package"] == "asset-inventory-persistence"
item["virtual_base_resolution"] = {"recorded_at": now(), "missing_base_lines_only_git_virtual_markers": True, "attribute_additions": additions}
item["final_head"] = git("rev-parse", "HEAD")
target = "65497b14cb5c24c6d780f675a70af3ee4019d8db"
manifest = "reports/runs/recovery_r17_graph_review1_recheck_20261016/artifact_manifest.json"
expected = "184e38e78839ebc53cac484d3681b5c59e68b54d4b2d2a948433fe6c58dc0b73"
assert hashlib.sha256((ROOT / manifest).read_bytes()).hexdigest() == expected
argv = ["git", "merge", "--no-ff", target, "-m", "G-E integrate reviewed evidence graph pointer selection"]
started = now()
with (RUN / "graph-pointer-selection_reviewed_merge.log").open("xb") as output:
    result = subprocess.run(argv, cwd=ROOT, stdout=output, stderr=subprocess.STDOUT, timeout=120)
receipt["packages"].append({"package": "graph-pointer-selection", "target_material_sha": target, "review_manifest_sha256": expected, "review_report": "reports/reviews/recovery/G-E-R17-evidence-graph-review-1-recheck.md", "review_report_sha256": hashlib.sha256((ROOT / "reports/reviews/recovery/G-E-R17-evidence-graph-review-1-recheck.md").read_bytes()).hexdigest(), "argv": argv, "started_at": started, "ended_at": now(), "merge_exit_code": result.returncode, "final_head": git("rev-parse", "HEAD")})
receipt["ended_at"] = now()
path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
assert result.returncode == 0, "root must inspect any remaining graph merge conflict"
print(json.dumps({"head": git("rev-parse", "HEAD"), "merged_components": len(receipt["packages"]), "push_attempts": 0}))
