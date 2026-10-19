"""Resolve exact qualified names and independently index the fixed product source."""

import hashlib
import json
from pathlib import Path
import subprocess
import time
from datetime import datetime
from zoneinfo import ZoneInfo

RUN = Path(__file__).resolve().parent
PREFIX = ["wsl.exe", "--exec", "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp", "cli", "--json"]
TOOL = "r06-restart-review1-bae"
SOURCE = "r06-restart-review1-e310-src"


def main():
    commands = [
        ("deploy_exact", ["trace_path", "--project", TOOL, "--function-name", TOOL + ".reports.runs.recovery_r06_live_restart_preparation_20261016.deploy_runtime_entry.load_owned_application", "--direction", "outbound", "--depth", "2", "--format", "json", "--include-evidence", "true"]),
        ("fence_exact", ["trace_path", "--project", TOOL, "--function-name", TOOL + ".reports.runs.recovery_r06_live_restart_preparation_20261016.task_fence.require_producer_slot", "--direction", "both", "--depth", "2", "--format", "json", "--include-evidence", "true"]),
        ("e310_index", ["index_repository", "--repo-path", "/mnt/d/wt/r06-live-e310-20261016/backend/src", "--name", SOURCE, "--mode", "fast", "--persistence", "false"]),
        ("e310_poll_search", ["search_graph", "--project", SOURCE, "--name-pattern", "poll_due_public_sources", "--format", "json"]),
        ("e310_poll_trace", ["trace_path", "--project", SOURCE, "--function-name", SOURCE + ".ai_intel.workers.runtime.poll_due_public_sources", "--direction", "outbound", "--depth", "2", "--format", "json", "--include-evidence", "true"]),
        ("e310_consume_trace", ["trace_path", "--project", SOURCE, "--function-name", SOURCE + ".ai_intel.workers.runtime.consume_job", "--direction", "outbound", "--depth", "2", "--format", "json", "--include-evidence", "true"]),
    ]
    receipts = []
    for name, arguments in commands:
        started, clock = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(), time.monotonic()
        result = subprocess.run(PREFIX + arguments, capture_output=True, timeout=120)
        raw = result.stdout + result.stderr
        (RUN / ("cbm_" + name + ".log")).write_bytes(raw)
        receipts.append({"name": name, "command": PREFIX + arguments, "started_at": started,
                         "ended_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
                         "seconds": time.monotonic() - clock, "exit_code": result.returncode,
                         "raw_sha256": hashlib.sha256(raw).hexdigest()})
    (RUN / "cbm_trace_commands.json").write_text(json.dumps(receipts, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipts))


if __name__ == "__main__":
    main()
