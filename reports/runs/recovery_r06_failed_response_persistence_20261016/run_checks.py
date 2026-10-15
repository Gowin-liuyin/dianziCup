"""Capture this worktree's offline checks without connection strings in artifacts."""

from __future__ import annotations

import json
import hashlib
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]


def capture(label: str, arguments: list[str], cwd: Path) -> int:
    started = datetime.now().astimezone().isoformat()
    environment = dict(os.environ, PYTHONUTF8="1")
    for key in ("TEST_DATABASE_URL", "TEST_REDIS_URL", "DIANZI_TEST_RUN_ID"):
        environment.pop(key, None)
    completed = subprocess.run(arguments, cwd=cwd, env=environment, capture_output=True)
    (RUN / (label + ".log")).write_bytes(completed.stdout + completed.stderr)
    receipt = {
        "argv": arguments,
        "cwd": str(cwd),
        "started_at": started,
        "finished_at": datetime.now().astimezone().isoformat(),
        "exit_code": completed.returncode,
        "code_base_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "source_hashes": {
            str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (ROOT / "backend/src/ai_intel/ingestion").glob("source_*receipt*.py")
        },
    }
    (RUN / (label + ".json")).write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps({"label": label, "exit_code": completed.returncode}))
    return completed.returncode


if __name__ == "__main__":
    if sys.argv[1] == "cbm":
        prefix = [
            "wsl", "--exec", "env",
            "XDG_CACHE_HOME=/tmp/dianzi-cbm-r06-failed-response-cache",
            "CBM_ALLOWED_ROOT=/mnt/d/wt/r06-failed-response-persistence/backend/src",
            "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp", "cli",
        ]
        commands = [
            ("cbm_index", ["index_repository", "--repo-path", "/mnt/d/wt/r06-failed-response-persistence/backend/src", "--name", "r06-failed-response-src", "--mode", "full"]),
            ("cbm_schema", ["get_graph_schema", "--project", "r06-failed-response-src"]),
            ("cbm_architecture", ["get_architecture", "--project", "r06-failed-response-src", "--aspects", "overview"]),
        ]
        commands.extend(("cbm_trace_" + name, ["trace_path", "--project", "r06-failed-response-src", "--function-name", name, "--direction", "both", "--depth", "3", "--limit", "80", "--max-output-tokens", "4000"]) for name in ("_fetch_catalog_page", "build_source_page_handler", "execute_job", "register_response_content"))
        for label, arguments in commands:
            if capture(label, prefix + arguments, ROOT):
                raise SystemExit(1)
    else:
        raise SystemExit(capture(sys.argv[1], sys.argv[2:], ROOT / "backend"))
