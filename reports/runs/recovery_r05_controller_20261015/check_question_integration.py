"""记录R05接线检查；秘密连接只传子进程环境。"""

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
environment = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
base = ["uv", "run", "--frozen", "--extra", "semantic"]
if label == "gb_security_exact_manifest_recheck":
    command = base + ["pytest", "tests/security/test_t06_authentication_and_scope.py::test_audit_and_sources_carry_no_secret_values_t06_c06", "--no-cov", "-q", "--junitxml=" + str(run / (label + ".xml"))]
elif label == "gb_pure_regression":
    command = base + ["pytest", "tests/unit", "tests/contract", "tests/security", "-m", "not real_pg", "-q", "--junitxml=" + str(run / (label + ".xml"))]
elif label.startswith("questions_api_pg"):
    private = subprocess.run(["wsl", "-d", "Ubuntu-22.04", "-u", "root", "--exec", "cat", "/tmp/dianzi-docker-static-r01-20261014/runtime/r05-pgvector/connection.json"], capture_output=True, text=True, check=True, timeout=10)
    environment["TEST_DATABASE_URL"] = json.loads(private.stdout)["TEST_DATABASE_URL"]
    environment["DIANZI_TEST_RUN_ID"] = "r05_pgvector_20261015"
    command = base + ["pytest", "tests/integration/test_r05_question_api_pg.py", "tests/unit/test_r05_question_routes.py", "tests/contract/test_r05_question_contracts.py", "--no-cov", "-q", "--junitxml=" + str(run / (label + ".xml"))]
    if label.endswith("sqllease"):
        command += ["-k", "default_application_post_get_citations_and_restart"]
elif label.startswith("questions_source_regression"):
    command = base + ["pytest", "tests/unit", "tests/security/test_r03_network_transport.py", "tests/contract/test_r05_generation_wire.py", "-q", "--junitxml=" + str(run / (label + ".xml"))]
elif label == "questions_unit":
    command = base + ["pytest", "tests/unit", "-q", "--junitxml=" + str(run / (label + ".xml"))]
elif label == "questions_static":
    command = base + ["mypy", "src"]
elif label == "questions_related":
    command = base + ["pytest", "tests/unit/test_r05_grounded_answer.py", "tests/contract/test_r05_grounded_answer_contract.py", "tests/contract/test_r05_question_contracts.py", "tests/unit/test_r05_evidence_chunks.py", "--no-cov", "-q", "--junitxml=" + str(run / (label + ".xml"))]
elif label.startswith("questions_graph_index"):
    command = ["wsl", "-d", "Ubuntu-22.04", "-u", "root", "--exec", "/usr/bin/env", "CBM_CACHE_DIR=/tmp/dianzi-cbm-root-r05-qa-20261015", "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp", "cli", "--json", "index_repository", "--repo-path", "/mnt/d/dianzi/backend/src", "--name", "dianzi-root-r05-qa-wired", "--mode", "fast"]
elif label == "questions_graph_trace_auth":
    command = ["wsl", "-d", "Ubuntu-22.04", "-u", "root", "--exec", "/usr/bin/env", "CBM_CACHE_DIR=/tmp/dianzi-cbm-root-r05-qa-20261015", "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp", "cli", "--json", "trace_path", "--project", "dianzi-root-r05-qa-wired", "--function-name", "lock_authenticated_scope", "--direction", "both", "--include-tests", "true"]
else:
    raise ValueError("unknown bounded check")
started = datetime.now(clock).isoformat(timespec="seconds")
result = subprocess.run(command, cwd=root / "backend", env=environment, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=240)
output = result.stdout + result.stderr
(run / (label + ".log")).write_text(output, encoding="utf-8")
record = {"started_at": started, "ended_at": datetime.now(clock).isoformat(timespec="seconds"), "command": command, "cwd": str(root / "backend"), "exit_code": result.returncode, "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(), "source_tree_state": "root R05 question integration working diff; frozen SHA follows"}
(run / (label + ".json")).write_text(json.dumps(record, indent=2), encoding="utf-8")
print(json.dumps(record))
print(json.dumps(output[-2200:]))
raise SystemExit(result.returncode)
