"""原有PG权限/任务回归使用新建独立测试库，不升级旧G-A复核库。"""

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
label = sys.argv[1] if len(sys.argv) > 1 else "gb_pg_security"
assert label in {"gb_pg_security", "gb_pg_security_recheck"}
receipt = run / (label + ".json")
assert not receipt.exists()
clock = ZoneInfo("Asia/Shanghai")
started = datetime.now(clock).isoformat(timespec="seconds")
private = subprocess.run(["wsl", "-d", "Ubuntu-22.04", "-u", "root", "--exec", "cat", "/tmp/dianzi-docker-static-r01-20261014/runtime/r05-pgvector/connection.json"], capture_output=True, text=True, check=True, timeout=10)
base_url = make_url(json.loads(private.stdout)["TEST_DATABASE_URL"])
assert base_url.database == "test_dianzi_r05_pgvector_20261015"
if label == "gb_pg_security_recheck":
    database = json.loads((run / "gb_pg_security_allocation.json").read_text(encoding="utf-8"))["database"]
    assert database.startswith("test_dianzi_gb_security_") and database.replace("_", "").isalnum()
else:
    assert not (run / "gb_pg_security_allocation.json").exists()
    database = "test_dianzi_gb_security_20261015_" + uuid4().hex[:8]
    with create_engine(base_url, isolation_level="AUTOCOMMIT").connect() as connection:
        assert connection.scalar(text("SELECT current_database()")) == base_url.database
        assert not connection.scalar(text("SELECT 1 FROM pg_database WHERE datname=:name"), {"name": database})
        connection.execute(text('CREATE DATABASE "' + database + '"'))
    (run / "gb_pg_security_allocation.json").write_text(json.dumps({"created_at": datetime.now(clock).isoformat(timespec="seconds"), "database": database, "scope": "root G-B legacy authorization and outbox regression only; no production or prior review DB", "removed_or_downgraded": False}, indent=2), encoding="utf-8")
environment = dict(os.environ, TEST_DATABASE_URL=base_url.set(database=database).render_as_string(hide_password=False), DIANZI_TEST_RUN_ID=database.removeprefix("test_dianzi_"), PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
command = ["uv", "run", "--frozen", "--extra", "semantic", "pytest", "tests/security/test_r02_auth_state_boundaries.py", "tests/security/test_r03_executor_authorization.py", "tests/contract/test_t07_jobs_outbox.py", "--no-cov", "-q", "--junitxml=" + str(run / (label + ".xml"))]
result = subprocess.run(command, cwd=root / "backend", env=environment, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
output = result.stdout + result.stderr
for secret in (environment["TEST_DATABASE_URL"], base_url.password or ""):
    if secret:
        output = output.replace(secret, "[REDACTED]")
(run / (label + ".log")).write_text(output, encoding="utf-8")
record = {"started_at": started, "ended_at": datetime.now(clock).isoformat(timespec="seconds"), "command": command, "cwd": str(root / "backend"), "database": database, "exit_code": result.returncode, "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()}
receipt.write_text(json.dumps(record, indent=2), encoding="utf-8")
print(json.dumps(record))
print(json.dumps(output[-1800:]))
raise SystemExit(result.returncode)
