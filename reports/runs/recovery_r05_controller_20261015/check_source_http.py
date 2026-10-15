"""来源HTTP修复只在本批新隔离库运行，凭据只传子进程环境。"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

root = Path(__file__).resolve().parents[3]
run = Path(__file__).resolve().parent
label = sys.argv[1]
assert label in {"source_http_red", "source_http_green", "source_http_regression"}
receipt = run / (label + ".json")
assert not receipt.exists()
clock = ZoneInfo("Asia/Shanghai")
started = datetime.now(clock).isoformat(timespec="seconds")
private = subprocess.run(["wsl", "-d", "Ubuntu-22.04", "-u", "root", "--exec", "cat", "/tmp/dianzi-docker-static-r01-20261014/runtime/r05-pgvector/connection.json"], capture_output=True, text=True, check=True, timeout=10)
base_url = make_url(json.loads(private.stdout)["TEST_DATABASE_URL"])
assert base_url.database == "test_dianzi_r05_pgvector_20261015"
allocation = run / "source_http_test_allocation.json"
if label == "source_http_red":
    assert not allocation.exists()
    database = "test_dianzi_gb_source_http_20261015_" + uuid4().hex[:8]
    with create_engine(base_url, isolation_level="AUTOCOMMIT", connect_args={"connect_timeout": 5}).connect() as connection:
        assert not connection.scalar(text("SELECT 1 FROM pg_database WHERE datname=:database"), {"database": database})
        connection.execute(text('CREATE DATABASE "' + database + '"'))
    allocation.write_text(json.dumps({"created_at": datetime.now(clock).isoformat(timespec="seconds"), "database": database, "scope": "source HTTP idempotency and transaction authorization only; no existing database migration or downgrade"}, indent=2) + "\n", encoding="utf-8")
else:
    database = json.loads(allocation.read_text(encoding="utf-8"))["database"]
    assert database.startswith("test_dianzi_gb_source_http_") and database.replace("_", "").isalnum()
environment = dict(os.environ, TEST_DATABASE_URL=base_url.set(database=database).render_as_string(hide_password=False), DIANZI_TEST_RUN_ID=database.removeprefix("test_dianzi_"), PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
paths = ["tests/integration/test_r04_source_http_idempotency_pg.py"]
if label == "source_http_regression":
    paths = ["tests/unit", "tests/contract", "tests/security"]
command = ["uv", "run", "--frozen", "--extra", "semantic", "pytest", *paths, "-q", "--junitxml=" + str(run / (label + ".xml"))]
if label != "source_http_regression":
    command.append("--no-cov")
else:
    command += ["-m", "not real_pg"]
result = subprocess.run(command, cwd=root / "backend", env=environment, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=240)
output = result.stdout + result.stderr
for secret in (environment["TEST_DATABASE_URL"], base_url.password or ""):
    if secret:
        output = output.replace(secret, "[REDACTED]")
(run / (label + ".log")).write_text(output, encoding="utf-8")
receipt.write_text(json.dumps({"started_at": started, "ended_at": datetime.now(clock).isoformat(timespec="seconds"), "cwd": str(root / "backend"), "argv": command, "exit_code": result.returncode, "database": database, "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()}, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"label": label, "exit_code": result.returncode, "tail": output[-1400:]}))
raise SystemExit(result.returncode)
