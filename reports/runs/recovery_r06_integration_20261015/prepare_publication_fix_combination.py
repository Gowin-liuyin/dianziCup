"""Freeze the two non-overlapping fixes for the original independent reviewer."""

import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
WORKSPACE = Path("D:/wt/r07-pub-combined")
RUN = Path(__file__).parent
assert not WORKSPACE.exists()
steps = [
    (ROOT, ["git", "worktree", "add", "-b", "codex/r07-publication-fix-combination", str(WORKSPACE), "ad2158258e1107ed68fed4287d7da85cd6e9163f"]),
    (WORKSPACE, ["git", "cherry-pick", "a80408fb35addf35c04a91d255f20fb9a987423e"]),
    (WORKSPACE, ["git", "cherry-pick", "2ba07cbfbdb5d24d0bf3214dcf522ddfce3ed184"]),
]
receipt = {"started_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"), "scope": "publication ACL/lock plus CVSS authority; independent targeted recheck required", "steps": [], "accepted": False, "push_attempts": 0}
for index, (cwd, argv) in enumerate(steps):
    with (RUN / f"publication_fix_combination_{index}.log").open("xb") as output:
        result = subprocess.run(argv, cwd=cwd, stdout=output, stderr=subprocess.STDOUT, timeout=120)
    receipt["steps"].append({"cwd": str(cwd), "argv": argv, "exit_code": result.returncode})
    (RUN / "publication_fix_combination_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    if result.returncode:
        raise SystemExit(result.returncode)
receipt["ended_at"] = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
receipt["head"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=WORKSPACE, text=True).strip()
receipt["tree"] = subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], cwd=WORKSPACE, text=True).strip()
receipt["source_clean"] = not subprocess.check_output(["git", "status", "--porcelain", "--", "backend/src", "backend/tests"], cwd=WORKSPACE, text=True).strip()
assert receipt["source_clean"]
(RUN / "publication_fix_combination_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
print(json.dumps(receipt))
