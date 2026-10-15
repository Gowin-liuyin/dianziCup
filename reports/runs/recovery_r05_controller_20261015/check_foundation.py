"""主控R05基础检查，专用PG连接仅经子进程环境传递。"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

root = Path(__file__).resolve().parents[3]
run = Path(__file__).resolve().parent
label = sys.argv[1]
assert not (run / (label + ".json")).exists()
clock = ZoneInfo("Asia/Shanghai")
started = datetime.now(clock).isoformat(timespec="seconds")
environment = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
if label.startswith("vector_pg"):
    private = subprocess.run(["wsl", "-d", "Ubuntu-22.04", "-u", "root", "--exec", "cat", "/tmp/dianzi-docker-static-r01-20261014/runtime/r05-pgvector/connection.json"], capture_output=True, text=True, check=True, timeout=10)
    environment["TEST_DATABASE_URL"] = json.loads(private.stdout)["TEST_DATABASE_URL"]
    environment["DIANZI_TEST_RUN_ID"] = "r05_pgvector_20261015"
    command = ["uv", "run", "--frozen", "--extra", "semantic", "pytest", "tests/integration/test_r05_vector_persistence.py", "--no-cov", "-q", "--junitxml=" + str(run / (label + ".xml"))]
elif label.startswith("embedding_regression"):
    command = ["uv", "run", "--frozen", "--extra", "semantic", "pytest", "tests/unit/test_r05_embedding_boundaries.py", "tests/unit/test_r05_semantic.py", "tests/unit/test_r05_process_limits.py", "tests/contract/test_r05_semantic_contract.py", "tests/contract/test_t18_model_clients.py", "--no-cov", "-q", "--junitxml=" + str(run / (label + ".xml"))]
elif label == "schema_regression":
    private = subprocess.run(["wsl", "-d", "Ubuntu-22.04", "-u", "root", "--exec", "cat", "/tmp/dianzi-docker-static-r01-20261014/runtime/r05-pgvector/connection.json"], capture_output=True, text=True, check=True, timeout=10)
    environment["TEST_DATABASE_URL"] = json.loads(private.stdout)["TEST_DATABASE_URL"]
    environment["DIANZI_TEST_RUN_ID"] = "r05_pgvector_20261015"
    command = ["uv", "run", "--frozen", "--extra", "semantic", "pytest", "tests/integration/test_r02_schema_migration.py", "--no-cov", "-q", "--junitxml=" + str(run / (label + ".xml"))]
elif label == "static":
    command = ["uv", "run", "--frozen", "--extra", "semantic", "mypy", "src"]
elif label.startswith("graph_"):
    base = ["wsl", "-d", "Ubuntu-22.04", "-u", "root", "--exec", "/usr/bin/env", "CBM_CACHE_DIR=/tmp/dianzi-cbm-root-r05-qa-20261015", "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp", "cli", "--json"]
    argument = {"graph_index": ["index_repository", "--repo-path", "/mnt/d/dianzi/backend/src", "--name", "dianzi-root-r05-qa", "--mode", "fast"],
                "graph_schema": ["get_graph_schema", "--project", "dianzi-root-r05-qa"],
                "graph_trace": ["trace_path", "--project", "dianzi-root-r05-qa", "--function-name", "validate_embedding_batch", "--direction", "both", "--include-tests", "true"]}[label]
    command = base + argument
else:
    raise ValueError("unknown bounded check")
result = subprocess.run(command, cwd=root / "backend", env=environment, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
(run / (label + ".log")).write_text(result.stdout + result.stderr, encoding="utf-8")
record = {"started_at": started, "ended_at": datetime.now(clock).isoformat(timespec="seconds"),
          "command": command, "cwd": str(root / "backend"), "exit_code": result.returncode,
          "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
          "source_tree_state": "root R05 foundation working diff; freeze code SHA follows"}
(run / (label + ".json")).write_text(json.dumps(record, indent=2), encoding="utf-8")
print(json.dumps(record))
print(json.dumps((result.stdout + result.stderr)[-2500:]))
raise SystemExit(result.returncode)
