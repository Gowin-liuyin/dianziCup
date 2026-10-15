"""在主控独立候选WT冻结来源限流与原始响应头边界。"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

root = Path("C:/Users/yinha/.codex/worktrees/r04-rate-limits-candidate/dianzi")
run = Path(__file__).resolve().parent
group = sys.argv[1]
label = "source_rate_candidate_" + group
assert not (run / (label + ".json")).exists()
environment = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
clock = ZoneInfo("Asia/Shanghai")
started = datetime.now(clock).isoformat(timespec="seconds")
if group == "parser_red":
    command = ["uv", "run", "--frozen", "--extra", "semantic", "pytest", "tests/security/test_r03_network_transport.py::test_transport_errors_and_tracebacks_never_include_credential_values", "--no-cov", "-q", "--junitxml=" + str(run / (label + ".xml"))]
elif group in {"test", "parser_recheck"}:
    command = ["uv", "run", "--frozen", "--extra", "semantic", "pytest", "tests/unit/test_r04_source_rate_limits.py", "tests/unit/test_r04_source_jobs.py", "tests/security/test_r03_network_transport.py", "tests/security/test_r05_transport_timeouts.py", "tests/contract/test_t08_network_redirects.py", "--no-cov", "-q", "--junitxml=" + str(run / (label + ".xml"))]
elif group == "pg":
    private = subprocess.run(["wsl", "-d", "Ubuntu-22.04", "-u", "root", "--exec", "cat", "/tmp/dianzi-docker-static-r01-20261014/runtime/r05-pgvector/connection.json"], capture_output=True, text=True, check=True, timeout=10)
    environment["TEST_DATABASE_URL"] = json.loads(private.stdout)["TEST_DATABASE_URL"]
    environment["DIANZI_TEST_RUN_ID"] = "r05_pgvector_20261015"
    command = ["uv", "run", "--frozen", "--extra", "semantic", "pytest", "tests/integration/test_r04_source_jobs_pg.py", "--no-cov", "-q", "--junitxml=" + str(run / (label + ".xml"))]
elif group == "static":
    command = ["uv", "run", "--frozen", "--extra", "semantic", "mypy", "src"]
elif group == "index":
    command = ["wsl", "-d", "Ubuntu-22.04", "-u", "root", "--exec", "/usr/bin/env", "CBM_CACHE_DIR=/tmp/dianzi-cbm-root-r04-rate-candidate-20261015", "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp", "cli", "--json", "index_repository", "--repo-path", "/mnt/c/Users/yinha/.codex/worktrees/r04-rate-limits-candidate/dianzi/backend/src", "--name", "dianzi-r04-rate-candidate", "--mode", "fast"]
else:
    raise ValueError("unknown bounded check")
result = subprocess.run(command, cwd=root / "backend", env=environment, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
(run / (label + ".log")).write_text(result.stdout + result.stderr, encoding="utf-8")
record = {"started_at": started, "ended_at": datetime.now(clock).isoformat(timespec="seconds"), "command": command,
          "cwd": str(root / "backend"), "exit_code": result.returncode,
          "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
          "scope": "candidate working diff; root source-rate application and original header multiplicity guard; no paid or external GET"}
(run / (label + ".json")).write_text(json.dumps(record, indent=2), encoding="utf-8")
print(json.dumps(record))
print(json.dumps((result.stdout + result.stderr)[-2000:]))
raise SystemExit(result.returncode)
