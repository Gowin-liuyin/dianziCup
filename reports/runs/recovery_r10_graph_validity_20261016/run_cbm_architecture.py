"""保留 CBM CLI 参数拒绝记录后，按实际 help 修正 architecture 参数。"""

import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
CLI = ["wsl", "-d", "Ubuntu-22.04", "-u", "root", "--", "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp", "cli"]
receipts = []
for label, arguments in [
    ("cbm_architecture_help", ["get_architecture", "--help"]),
    ("cbm_architecture_recheck", ["get_architecture", "--project", "r10_pg_graph_backend", "--aspects", "all"]),
]:
    assert not (RUN / (label + ".log")).exists()
    command = [*CLI, *arguments]
    started = datetime.now(timezone(timedelta(hours=8))).isoformat()
    result = subprocess.run(command, cwd=ROOT, capture_output=True)
    (RUN / (label + ".log")).write_bytes(result.stdout + result.stderr)
    receipts.append({"command": command, "cwd": str(ROOT), "started_at": started, "finished_at": datetime.now(timezone(timedelta(hours=8))).isoformat(), "exit_code": result.returncode})
    print(json.dumps({"label": label, "exit_code": result.returncode}))
(RUN / "cbm_architecture_commands.json").write_text(json.dumps(receipts, ensure_ascii=False, indent=2), encoding="utf-8")
