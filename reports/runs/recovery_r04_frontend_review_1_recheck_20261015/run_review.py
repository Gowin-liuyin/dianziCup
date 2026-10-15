"""Execute fixed frontend review checks without application credentials."""

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

WORKTREE = Path(r"C:\Users\yinha\.codex\worktrees\recovery-r04-frontend-recheck\dianzi")
RUN = Path(__file__).resolve().parent
EXPECTED_SHA = "7f9b6f14e3c7c5ff451fab183f959a11d8daf114"
sys.stdout.reconfigure(encoding="utf-8")


def now():
    return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")


def main():
    label = sys.argv[1]
    cbm = ["wsl.exe", "--exec", "/usr/bin/env", "CBM_CACHE_DIR=/tmp/dianzi-cbm-r04-frontend-review-1-recheck-20261015", "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp", "cli", "--json"]
    commands = {
        "ci": ["npm.cmd", "ci"],
        "test": ["node", "node_modules/vitest/vitest.mjs", "run", "--reporter=default", "--reporter=junit", f"--outputFile.junit={RUN / 'test.xml'}"],
        "lint": ["npm.cmd", "run", "lint"],
        "typecheck": ["npm.cmd", "run", "typecheck"],
        "build": ["npm.cmd", "run", "build"],
        "audit": ["npm.cmd", "audit", "--json"],
        "browser": ["node", "node_modules/@playwright/test/cli.js", "test", "r04_fixture_contract.spec.ts", "r17_skip_link.spec.ts", "--reporter=json", f"--output={RUN / 'e2e-artifacts'}"],
        "background": ["node", "node_modules/@playwright/test/cli.js", "test", "r17_hacker_workspace.spec.ts", "--grep", "R17 dynamic background", "--reporter=json", f"--output={RUN / 'background-artifacts'}"],
        "cbm_index": [*cbm, "index_repository", "--repo-path", "/mnt/c/Users/yinha/.codex/worktrees/recovery-r04-frontend-recheck/dianzi/frontend/src", "--name", "dianzi-r04-frontend-review-1-recheck", "--mode", "fast", "--persistence", "false"],
        "cbm_schema": [*cbm, "get_graph_schema", "--project", "dianzi-r04-frontend-review-1-recheck", "--format", "json"],
        "cbm_trace": [*cbm, "trace_path", "--project", "dianzi-r04-frontend-review-1-recheck", "--function-name", "getEvidence", "--direction", "both", "--include-tests", "true", "--format", "json"],
    }
    command = commands[label]
    candidate = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=WORKTREE, text=True).strip()
    if candidate != EXPECTED_SHA:
        raise RuntimeError("fixed review candidate changed")
    receipt_path = RUN / f"{label}.command.json"
    if receipt_path.exists():
        raise FileExistsError("review evidence label already used")
    environment = dict(os.environ)
    environment.update(FORCE_COLOR="0", NO_COLOR="1", PYTHONUTF8="1")
    if label in {"browser", "background"}:
        environment.update(DIANZI_E2E_FRONTEND_URL="http://127.0.0.1:25304", PLAYWRIGHT_BROWSERS_PATH=r"C:\Users\yinha\.codex\cache\dianzi\r01_playwright_1248")
    started = now()
    result = subprocess.run(command, cwd=WORKTREE / "frontend", env=environment, capture_output=True, timeout=240)
    (RUN / f"{label}.stdout.log").write_bytes(result.stdout)
    (RUN / f"{label}.stderr.log").write_bytes(result.stderr)
    receipt = {"started_at": started, "ended_at": now(), "command": command, "cwd": str(WORKTREE / "frontend"), "exit_code": result.returncode, "candidate": candidate, "credential_input": "none"}
    receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps(receipt))
    if label in {"audit", "browser", "background"}:
        try:
            payload = json.loads(result.stdout)
            print(json.dumps(payload.get("metadata", payload.get("stats", {}))))
        except (ValueError, UnicodeError):
            print("Structured output unavailable; read preserved logs.")
    else:
        print(result.stdout.decode("utf-8", errors="replace")[-3500:])
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())

