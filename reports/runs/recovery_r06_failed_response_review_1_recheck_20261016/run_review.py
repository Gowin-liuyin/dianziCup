"""Capture independent commands and dedicated PostgreSQL checks without disclosing secrets."""

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
TARGET = "test_dianzi_r06_catalog_failure_review_fix1_20261016"
label, mode, *arguments = sys.argv[1:]
environment = dict(os.environ, PYTHONUTF8="1")
secrets = []
database_evidence = {}
if mode == "pg":
    from sqlalchemy import create_engine, inspect, text
    from sqlalchemy.engine import make_url

    captured = subprocess.check_output([
        "wsl", "-d", "Ubuntu-22.04", "-u", "root", "--", "cat",
        "/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json",
    ], text=True, timeout=15)
    configuration = json.loads(captured)
    url = make_url(configuration["TEST_DATABASE_URL"])
    assert url.database == configuration["postgres_database"] and url.database.startswith("test_")
    dedicated = url.set(database=TARGET)
    environment.update(TEST_DATABASE_URL=dedicated.render_as_string(hide_password=False), DIANZI_TEST_RUN_ID="r06_catalog_failure_review_fix1_20261016")
    sys.path.insert(0, str(ROOT))
    from scripts.dev import require_isolated_test_database
    require_isolated_test_database(environment)
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT", connect_args={"connect_timeout": 5})
    with admin.connect() as connection:
        present = connection.scalar(text("SELECT EXISTS(SELECT 1 FROM pg_database WHERE datname=:name)"), {"name": TARGET})
        if not present:
            connection.execute(text("CREATE DATABASE test_dianzi_r06_catalog_failure_review_fix1_20261016"))
    admin.dispose()
    engine = create_engine(dedicated, connect_args={"connect_timeout": 5})
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT current_database()")) == TARGET
        before = inspect(connection).get_table_names(schema="public")
        assert before == []
    environment.update(TEST_DATABASE_URL=dedicated.render_as_string(hide_password=False), DIANZI_TEST_RUN_ID="r06_catalog_failure_review_fix1_20261016")
    environment.pop("TEST_REDIS_URL", None)
    secrets = [environment["TEST_DATABASE_URL"], url.password]
    database_evidence = {"database": TARGET, "created": not present, "public_before": before}
if mode in {"pg", "pure"}:
    argv = [sys.executable, "-m", "pytest", *arguments, "--no-cov", "-q", "--tb=short", "--junitxml=" + str(RUN / (label + ".xml"))]
    cwd = ROOT / "backend"
elif mode == "python":
    argv = [sys.executable, *arguments]
    cwd = ROOT / "backend"
else:
    argv, cwd = arguments, ROOT
started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()
sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
completed = subprocess.run(argv, cwd=cwd, env=environment, capture_output=True)
output = completed.stdout + completed.stderr
for secret in secrets:
    if secret:
        output = output.replace(secret.encode(), b"[redacted]")
(RUN / (label + ".log")).write_bytes(output)
if mode == "pg":
    with engine.connect() as connection:
        after = inspect(connection).get_table_names(schema="public")
    assert before == after == []
    database_evidence["public_after"] = after
    engine.dispose()
receipt = {"argv": argv, "cwd": str(cwd), "started_at": started, "finished_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(), "exit_code": completed.returncode, "code_sha": sha, **database_evidence}
(RUN / (label + ".json")).write_text(json.dumps(receipt, indent=2, ensure_ascii=False), encoding="utf-8")
print(json.dumps({"label": label, "exit_code": completed.returncode}))
raise SystemExit(completed.returncode)
