"""保存当前根分支共享边界的真实代码索引与调用方查询。"""

import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
ZONE = ZoneInfo("Asia/Shanghai")
PROJECT = "dianzi-root-boundary-20261016-1636"
PREFIX = ["wsl", "-d", "Ubuntu-22.04", "--", "env", "XDG_CACHE_HOME=/tmp/dianzi-cbm-root-boundary-20261016-1636", "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp", "cli", "--json"]
source = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
commands = [
    ("root_boundary_schema_retry1", ["get_graph_schema", "--project", PROJECT]),
    ("root_assessment_callers_retry1", ["trace_path", "--project", PROJECT, "--function-name", PROJECT + ".ai_intel.assessment.assessment_service.AssessmentService.prepare", "--direction", "both", "--depth", "2", "--max-output-tokens", "2500"]),
]
receipts = []
for name, arguments in commands:
    started = datetime.now(ZONE).isoformat(timespec="seconds")
    result = subprocess.run(PREFIX + arguments, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60)
    ended = datetime.now(ZONE).isoformat(timespec="seconds")
    (RUN / (name + ".log")).write_bytes(result.stdout)
    receipt = {"started_at": started, "ended_at": ended, "source_sha": source, "command": PREFIX + arguments, "cwd": str(ROOT), "exit_code": result.returncode, "log": name + ".log"}
    receipts.append(receipt)
    print(json.dumps(receipt, ensure_ascii=True))
    if result.returncode:
        break
(RUN / "root_boundary_index_retry1_receipts.json").write_text(json.dumps(receipts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
raise SystemExit(0 if all(item["exit_code"] == 0 for item in receipts) else 1)
