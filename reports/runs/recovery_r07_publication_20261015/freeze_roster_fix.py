"""Freeze only the reviewed-scope roster guard and its regression, retaining raw logs."""

import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
files = [
    "backend/src/ai_intel/enrichment/publication.py",
    "backend/tests/integration/test_r07_enrichment_publication_pg.py",
    "docs/decisions/CR-R07_multisource_enrichment_publication.md",
]
at = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
before = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
subprocess.run(["git", "diff", "--check", "--", *files], cwd=ROOT, check=True)
assert not subprocess.check_output(["git", "diff", "--cached", "--name-only"], cwd=ROOT, text=True).strip()
subprocess.run(["git", "add", "--", *files], cwd=ROOT, check=True)
staged = subprocess.check_output(["git", "diff", "--cached", "--name-only"], cwd=ROOT, text=True).splitlines()
assert set(staged) == set(files)
with (RUN / "roster_guard_staged.diff").open("wb") as output:
    subprocess.run(["git", "diff", "--cached"], cwd=ROOT, stdout=output, check=True)
with (RUN / "roster_guard_commit.log").open("wb") as output:
    subprocess.run(["git", "commit", "-m", "G-C R07 reject incomplete current source rosters on publication"], cwd=ROOT, stdout=output, stderr=subprocess.STDOUT, check=True)
receipt = {"at": at, "before": before, "after": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(), "files": staged, "scope": "awaiting new independent review; no worker/API/live gate"}
(RUN / "roster_guard_commit_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
print(json.dumps(receipt))
