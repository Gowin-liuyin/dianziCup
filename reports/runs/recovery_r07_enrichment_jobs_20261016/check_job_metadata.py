"""Verify the actual forward migration in an isolated database without exposing its DSN."""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
label = sys.argv[1] if len(sys.argv) > 1 else "metadata_pg"
assert label.replace("_", "").isalnum()
started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
private = subprocess.run(
    ["wsl.exe", "-d", "Ubuntu-22.04", "-u", "root", "--exec", "cat", "/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json"],
    capture_output=True,
    check=True,
)
url = make_url(json.loads(private.stdout)["TEST_DATABASE_URL"])
assert url.host in {"127.0.0.1", "localhost"} and url.port == 25432
assert url.database.startswith("test_dianzi_")
run_id = "r06_catalog_r07_enrichment_metadata_20261016"
database = "test_dianzi_" + run_id
engine = create_engine(url, isolation_level="AUTOCOMMIT")
try:
    with engine.connect() as connection:
        if not connection.scalar(text("SELECT 1 FROM pg_database WHERE datname=:name"), {"name": database}):
            connection.execute(text('CREATE DATABASE "' + database + '"'))
finally:
    engine.dispose()
environment = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONPATH=str(ROOT / "backend/src"))
environment.pop("TEST_REDIS_URL", None)
environment["TEST_DATABASE_URL"] = url.set(database=database).render_as_string(hide_password=False)
environment["DIANZI_TEST_RUN_ID"] = run_id
argv = [str(ROOT / "backend/.venv/Scripts/python.exe"), "-m", "pytest", "tests/integration/test_r07_enrichment_job_metadata_pg.py", "--no-cov", "-q", "--junitxml=" + str(RUN / (label + ".xml"))]
with (RUN / (label + ".log")).open("xb") as output:
    result = subprocess.run(argv, cwd=ROOT / "backend", env=environment, stdout=output, stderr=subprocess.STDOUT, timeout=180)
receipt = {
    "started_at": started,
    "ended_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
    "cwd": str(ROOT / "backend"),
    "argv": argv,
    "exit_code": result.returncode,
    "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
    "code_state": "new uncommitted metadata/migration/test implementation; not frozen acceptance",
    "test_database": database,
    "scope": "real PG forward0017 migration, synthetic authenticated actor/source inputs; no external request",
}
(RUN / (label + ".json")).write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps({"exit_code": result.returncode, "test_database": database}))
raise SystemExit(result.returncode)
