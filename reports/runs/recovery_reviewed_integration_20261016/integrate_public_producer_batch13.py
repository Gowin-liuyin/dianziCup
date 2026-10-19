"""Import the frozen public producer without copying unknown workspace files."""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
SOURCE = "c18cd5ea7ac0848cad5f6ac9e3896b8517eb875d"
ALLOWED = {
    "backend/src/ai_intel/api/public_extension_reads.py",
    "backend/src/ai_intel/api/public_extension_routes.py",
    "backend/tests/contract/test_r18_public_producer_contract.py",
    "backend/tests/integration/test_r18_public_producer_fix1_pg.py",
    "backend/tests/integration/test_r18_public_producer_fix2_pg.py",
    "backend/tests/integration/test_r18_public_read_producer_pg.py",
    "backend/tests/security/test_r18_public_read_security.py",
    "backend/tests/unit/test_r18_public_producer_fix1_health.py",
    "backend/tests/unit/test_r18_public_producer_fix2_declared.py",
    "backend/tests/unit/test_r18_public_producer_fix3_origins.py",
    "backend/tests/unit/test_r18_public_read_boundaries.py",
}
started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
actual = set(subprocess.check_output(["git", "diff-tree", "--no-commit-id", "--name-only", "-r", SOURCE], cwd=ROOT, text=True).splitlines())
if actual != ALLOWED:
    raise RuntimeError("unexpected frozen scope")
items = []
for relative in sorted(ALLOWED):
    path = ROOT / relative
    if path.exists():
        raise RuntimeError("existing local file protected: " + relative)
    payload = subprocess.check_output(["git", "show", SOURCE + ":" + relative], cwd=ROOT)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    items.append({"path": relative, "source_sha": SOURCE, "sha256": hashlib.sha256(payload).hexdigest(), "bytes": len(payload), "source_git_blob": subprocess.check_output(["git", "rev-parse", SOURCE + ":" + relative], cwd=ROOT, text=True).strip()})
(RUN / "public_producer_batch13_inputs.json").write_text(json.dumps({"started_at": started, "ended_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"), "files": items, "default_mount": "not_run", "integration": "not_run", "whole_task_accepted": False}, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps({"files": len(items), "integration": "not_run"}))
