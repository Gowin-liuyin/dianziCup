"""只在内存捕获既有私有测试连接，执行本切片隔离数据库与质量检查。"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
PYTHON = sys.executable
RUN_ID = "r06_catalog_r10_graph_20261016"
DATABASE = "test_dianzi_" + RUN_ID
CONNECTION_FILE = "/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json"
FILES = [
    "src/ai_intel/knowledge/evidence_graph.py",
    "src/ai_intel/api/graph_routes.py",
    "tests/unit/test_r10_evidence_graph.py",
    "tests/contract/test_r10_graph_contract.py",
    "tests/security/test_r10_graph_boundary.py",
    "tests/integration/test_r10_evidence_graph_pg.py",
]
OFFSET = timezone(timedelta(hours=8))


def timestamp():
    return datetime.now(OFFSET).isoformat()


def main():
    label = os.environ.get("R10_CHECK_LABEL", "frozen")
    assert label in {"frozen", "recheck"}
    capture = subprocess.run(
        ["wsl", "-d", "Ubuntu-22.04", "-u", "root", "--", "cat", CONNECTION_FILE],
        capture_output=True, text=True, check=True,
    )
    private = json.loads(capture.stdout)
    original = make_url(private["TEST_DATABASE_URL"])
    assert original.database.startswith("test_dianzi_")
    assert original.username.startswith("test_")
    assert original.host == "127.0.0.1" and original.port == 25432
    engine = create_engine(original, isolation_level="AUTOCOMMIT", connect_args={"connect_timeout": 5})
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT current_database()")) == original.database
        assert connection.scalar(text("SELECT current_user")) == original.username
        if not connection.scalar(text("SELECT 1 FROM pg_database WHERE datname=:name"), {"name": DATABASE}):
            connection.execute(text('CREATE DATABASE "' + DATABASE + '"'))
    engine.dispose()
    environment = dict(os.environ)
    environment.update(
        PYTHONPATH=str(ROOT / "backend/src"),
        DIANZI_TEST_RUN_ID=RUN_ID,
        TEST_DATABASE_URL=original.set(database=DATABASE).render_as_string(hide_password=False),
    )
    commands = {
        "pure": [PYTHON, "-m", "pytest", "-o", "addopts=", *FILES[2:5], "-q", "--junitxml=" + str(RUN / ("pure_" + label + ".xml"))],
        "pg": [PYTHON, "-m", "pytest", "-o", "addopts=", FILES[5], "-q", "--junitxml=" + str(RUN / ("pg_" + label + ".xml"))],
        "regression": [PYTHON, "-m", "pytest", "-o", "addopts=", "tests/unit/test_r02_knowledge_publication_contract.py", "tests/unit/test_r02_knowledge_boundaries.py", "tests/unit/test_r02_dimension_publication_contract.py", "tests/contract/test_r07_signal_claim_values.py", "tests/integration/test_r07_signal_claim_values_pg.py", "tests/integration/test_r07_literature_target_scope_pg.py", "tests/integration/test_r02_relation_identity_regressions.py", "-q", "--junitxml=" + str(RUN / ("regression_" + label + ".xml"))],
        "ruff": [PYTHON, "-m", "ruff", "check", *FILES],
        "format": [PYTHON, "-m", "ruff", "format", "--check", *FILES],
        "mypy": [PYTHON, "-m", "mypy", *FILES[:2]],
    }
    chosen = sys.argv[1:] or list(commands)
    receipts = []
    for name in chosen:
        started = timestamp()
        completed = subprocess.run(commands[name], cwd=ROOT / "backend", env=environment, capture_output=True, text=True, encoding="utf-8", errors="replace")
        output = completed.stdout + completed.stderr
        output = output.replace(environment["TEST_DATABASE_URL"], "[redacted connection]").replace(original.password, "[redacted credential]")
        log_name = name + "_" + label + ".log"
        (RUN / log_name).write_text(output, encoding="utf-8")
        receipt = {"name": name, "command": commands[name], "cwd": str(ROOT / "backend"), "started_at": started, "finished_at": timestamp(), "exit_code": completed.returncode, "log": log_name, "data_mode": "fixture", "database": DATABASE, "code_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()}
        receipts.append(receipt)
        print(json.dumps({key: receipt[key] for key in ("name", "exit_code", "started_at", "finished_at")}), flush=True)
    (RUN / ("commands_" + label + ".json")).write_text(json.dumps(receipts, ensure_ascii=False, indent=2), encoding="utf-8")
    return max(item["exit_code"] for item in receipts)


if __name__ == "__main__":
    raise SystemExit(main())
