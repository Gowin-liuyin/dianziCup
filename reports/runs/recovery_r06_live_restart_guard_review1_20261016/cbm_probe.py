"""Run read-only CBM CLI queries with a private cache and no persistent repo artifact."""

import hashlib
import json
from pathlib import Path
import subprocess
import time
from datetime import datetime
from zoneinfo import ZoneInfo

RUN = Path(__file__).resolve().parent
PREFIX = ["wsl.exe", "--exec", "env", "XDG_CACHE_HOME=/tmp/r06-restart-review1-cbm",
          "XDG_CONFIG_HOME=/tmp/r06-restart-review1-cbm-config",
          "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp", "cli", "--json"]
PROJECT = "r06-restart-review1-bae"


def main():
    commands = [
        ("index_retry", ["index_repository", "--repo-path", "/mnt/d/wt/r06-live-restart-review1", "--name", PROJECT, "--mode", "fast", "--persistence", "false"]),
        ("schema", ["get_graph_schema", "--project", PROJECT, "--format", "json"]),
        ("fence_search", ["search_graph", "--project", PROJECT, "--name-pattern", "require_producer_slot", "--format", "json", "--limit", "10"]),
        ("deploy_trace", ["trace_path", "--project", PROJECT, "--function-name", "load_owned_application", "--direction", "outbound", "--depth", "2", "--format", "json", "--include-evidence", "true"]),
        ("poll_trace", ["trace_path", "--project", PROJECT, "--function-name", "ai_intel.workers.runtime.poll_due_public_sources", "--direction", "outbound", "--depth", "2", "--format", "json", "--include-evidence", "true"]),
    ]
    receipts = []
    for name, arguments in commands:
        started, clock = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(), time.monotonic()
        result = subprocess.run(PREFIX + arguments, capture_output=True, timeout=300)
        raw = result.stdout + result.stderr
        (RUN / ("cbm_" + name + ".log")).write_bytes(raw)
        receipts.append({"name": name, "command": PREFIX + arguments, "started_at": started,
                         "ended_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
                         "seconds": time.monotonic() - clock, "exit_code": result.returncode,
                         "raw_sha256": hashlib.sha256(raw).hexdigest()})
        if name == "index_retry" and result.returncode:
            break
    (RUN / "cbm_commands.json").write_text(json.dumps(receipts, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipts))


if __name__ == "__main__":
    main()
