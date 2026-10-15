"""Run only this package's checks with a private in-memory WSL connection."""

import json
import hashlib
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
TARGET = "test_dianzi_r06_catalog_failure_receipt_20261016"
captured = subprocess.check_output([
    "wsl", "-d", "Ubuntu-22.04", "-u", "root", "--", "cat",
    "/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json",
], text=True)
configuration = json.loads(captured)
url = make_url(configuration["TEST_DATABASE_URL"])
assert url.database == configuration["postgres_database"] and url.database.startswith("test_")
admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT", connect_args={"connect_timeout": 5})
with admin.connect() as connection:
    present = connection.scalar(text("SELECT EXISTS(SELECT 1 FROM pg_database WHERE datname=:name)"), {"name": TARGET})
    if not present:
        connection.execute(text("CREATE DATABASE test_dianzi_r06_catalog_failure_receipt_20261016"))
admin.dispose()
dedicated = url.set(database=TARGET)
engine = create_engine(dedicated, connect_args={"connect_timeout": 5})
with engine.connect() as connection:
    assert connection.scalar(text("SELECT current_database()")) == TARGET
    public_before = inspect(connection).get_table_names(schema="public")
    assert public_before == []
engine.dispose()
environment = dict(os.environ, TEST_DATABASE_URL=dedicated.render_as_string(hide_password=False), DIANZI_TEST_RUN_ID="r06_catalog_failure_receipt_20261016", PYTHONUTF8="1")
environment.pop("TEST_REDIS_URL", None)
label = sys.argv[1]
if label == "pg_baseline_red":
    environment["PYTHONPATH"] = "D:/dianzi/backend/src"
arguments = [sys.executable, "-m", "pytest", *sys.argv[2:], "--no-cov", "-q", "--tb=short", "--junitxml=" + str(RUN / (label + ".xml"))]
started = datetime.now().astimezone().isoformat()
code_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
source_hashes = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in (ROOT / "backend/src/ai_intel/ingestion").glob("source_*receipt*.py")}
completed = subprocess.run(arguments, cwd=ROOT / "backend", env=environment, capture_output=True)
output = completed.stdout + completed.stderr
for secret in (environment["TEST_DATABASE_URL"], url.password):
    if secret:
        output = output.replace(secret.encode(), b"[redacted]")
(RUN / (label + ".log")).write_bytes(output)
engine = create_engine(dedicated)
with engine.connect() as connection:
    public_after = inspect(connection).get_table_names(schema="public")
assert public_before == public_after == []
engine.dispose()
receipt = {"argv": arguments, "cwd": str(ROOT / "backend"), "started_at": started, "finished_at": datetime.now().astimezone().isoformat(), "exit_code": completed.returncode, "database": TARGET, "created": not present, "public_before": public_before, "public_after": public_after, "code_sha": code_sha, "source_hashes": source_hashes}
(RUN / (label + ".json")).write_text(json.dumps(receipt, indent=2), encoding="utf-8")
print(json.dumps({"label": label, "exit_code": completed.returncode, "database": TARGET}))
raise SystemExit(completed.returncode)
