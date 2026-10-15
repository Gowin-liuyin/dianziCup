"""Freeze only the reviewed repair combination and readable provenance addition."""

import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
paths = [
    "backend/src/ai_intel/enrichment/publication.py",
    "backend/tests/integration/test_r07_publication_rule_provenance_pg.py",
    "docs/decisions/CR-R07_multisource_enrichment_publication.md",
]
assert not subprocess.check_output(["git", "diff", "--cached", "--name-only"], cwd=ROOT)
started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
commands = [
    ["git", "diff", "--check", "--", *paths],
    ["git", "add", "--", *paths],
    ["git", "diff", "--cached", "--check"],
    ["git", "diff", "--cached", "--", *paths],
    ["git", "commit", "-m", "R07 retain readable rule and source context in publication receipts"],
]
for index, argv in enumerate(commands):
    result = subprocess.run(argv, cwd=ROOT, capture_output=True, timeout=60)
    (RUN / f"freeze_code_{index}.log").write_bytes(result.stdout + result.stderr)
    if result.returncode:
        raise SystemExit(result.returncode)
receipt = {
    "started_at": started,
    "ended_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
    "code_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
    "code_tree": subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], cwd=ROOT, text=True).strip(),
    "paths": paths,
    "commands": commands,
    "exit_code": 0,
    "pushes": 0,
    "product_acceptance": "awaiting_review",
}
(RUN / "freeze_code_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
print(json.dumps(receipt))
