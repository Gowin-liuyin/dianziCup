"""CBM官方CLI独立缓存的实际命令与时刻收据，只索引固定候选src。"""

import json
from pathlib import Path
import subprocess
from datetime import datetime
from zoneinfo import ZoneInfo

RUN = Path(__file__).resolve().parent
WT = Path("C:/Users/yinha/.codex/worktrees/r04-rate-limits-independent-review-1/dianzi")
BINARY = "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp"
PREFIX = ["wsl", "-u", "root", "--", "env",
          "CBM_CACHE_DIR=/tmp/dianzi-cbm-r04-rate-limits-review-1-20261015",
          "CBM_RUNTIME_DIR=/tmp/dianzi-cbm-r04-rate-limits-review-1-runtime-20261015", BINARY]
PROJECT = "r04-rate-limits-review-1-00261"
commands = [
    ("cbm_help", ["--help"]),
    ("cbm_index_help", ["cli", "index_repository", "--help"]),
    ("cbm_trace_help", ["cli", "trace_path", "--help"]),
    ("cbm_index_recorded", ["cli", "--json", "index_repository", "--repo-path",
                           "/mnt/c/Users/yinha/.codex/worktrees/r04-rate-limits-independent-review-1/dianzi/backend/src",
                           "--mode", "fast", "--name", PROJECT, "--persistence", "false"]),
    ("cbm_schema_recorded", ["cli", "--json", "get_graph_schema", "--project", PROJECT, "--format", "json"]),
    ("cbm_trace_failure_recorded", ["cli", "--json", "trace_path", "--project", PROJECT,
                                    "--function-name", "_http_failure", "--direction", "both", "--depth", "4", "--include-evidence", "true", "--format", "json"]),
    ("cbm_trace_gateway_recorded", ["cli", "--json", "trace_path", "--project", PROJECT,
                                    "--function-name", "build_source_page_handler", "--direction", "both", "--depth", "5", "--include-evidence", "true", "--format", "json"]),
    ("cbm_trace_transport_recorded", ["cli", "--json", "trace_path", "--project", PROJECT,
                                      "--function-name", "_HttpResponse", "--direction", "both", "--depth", "4", "--include-evidence", "true", "--format", "json"]),
]
receipts = []
for name, arguments in commands:
    started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
    result = subprocess.run(PREFIX + arguments, cwd=WT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    ended = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
    (RUN / (name + ".log")).write_text(result.stdout + result.stderr, encoding="utf-8")
    receipts.append({"name": name, "command": PREFIX + arguments, "cwd": str(WT),
                     "started_at": started, "ended_at": ended, "exit_code": result.returncode,
                     "log": str(RUN / (name + ".log"))})
(RUN / "cbm_commands.json").write_text(json.dumps(receipts, indent=2, ensure_ascii=False), encoding="utf-8")
print(json.dumps(receipts, ensure_ascii=False))
