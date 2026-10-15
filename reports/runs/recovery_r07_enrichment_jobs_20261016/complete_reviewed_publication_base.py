"""Resolve only exact raw-evidence attributes in the independently reviewed base merge."""

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


assert git("diff", "--name-only", "--diff-filter=U") == ".gitattributes"
assert git("rev-parse", "MERGE_HEAD") == "9e722c944cf83086ffd30ad24a708172c13da189"
base, ours, theirs = [git("show", f":{stage}:.gitattributes").splitlines() for stage in (1, 2, 3)]
assert set(base) <= set(ours) and set(base) <= set(theirs)
additional = [line for line in theirs if line not in ours]
assert all(not line or line.startswith("reports/") for line in additional)
assert not any(any(mark in line for mark in "?[]") for line in additional)
started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
(ROOT / ".gitattributes").write_text("\n".join(ours + additional) + "\n", encoding="utf-8", newline="\n")
subprocess.run(["git", "add", "--", ".gitattributes"], cwd=ROOT, check=True)
assert not git("diff", "--name-only", "--diff-filter=U")
subprocess.run(["git", "commit", "-m", "R07 workflow development uses independently reviewed publication repair and raw evidence"], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
receipt = {
    "started_at": started,
    "ended_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
    "merged_material": "9e722c944cf83086ffd30ad24a708172c13da189",
    "reviewed_code": "dc04d193185324f6913cde8efc40f4b238047dd8",
    "development_head": git("rev-parse", "HEAD"),
    "original_merge_exit_code": 1,
    "conflicts": [".gitattributes"],
    "added_evidence_lines": additional,
    "publication_blob": hashlib.sha256(subprocess.check_output(["git", "show", "HEAD:backend/src/ai_intel/enrichment/publication.py"], cwd=ROOT)).hexdigest(),
    "new_uncommitted_metadata": "separate candidate; not included in this base merge",
    "pushes": 0,
}
(RUN / "reviewed_publication_base_merge_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps(receipt))
