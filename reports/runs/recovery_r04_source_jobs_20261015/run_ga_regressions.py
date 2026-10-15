"""在主控专用隔离库复跑阶段审查发现的组合测试问题；不重置历史。"""

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from ai_intel.infrastructure.database import run_migrations

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
label = "ga_combined_regression_fixed"
receipt = RUN / (label + ".json")
assert not receipt.exists()
clock = ZoneInfo("Asia/Shanghai")
started = datetime.now(clock).isoformat(timespec="seconds")
result = subprocess.run(["wsl", "-d", "Ubuntu-22.04", "-u", "root", "--exec", "cat",
    "/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json"],
    check=True, capture_output=True, text=True, timeout=10)
source_url = make_url(json.loads(result.stdout)["TEST_DATABASE_URL"])
assert source_url.host == "127.0.0.1" and source_url.port == 25432
assert source_url.database == "test_dianzi_r01_20261014"
database = "test_dianzi_root_ga_regressions_20261015"
engine = create_engine(source_url, isolation_level="AUTOCOMMIT")
with engine.connect() as connection:
    if not connection.scalar(text("SELECT 1 FROM pg_database WHERE datname=:name"), {"name": database}):
        connection.execute(text('CREATE DATABASE "' + database + '"'))
engine.dispose()
database_url = source_url.set(database=database).render_as_string(hide_password=False)
run_migrations(database_url, "head")
environment = dict(os.environ, TEST_DATABASE_URL=database_url,
    DIANZI_TEST_RUN_ID="root_ga_regressions_20261015", PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
for name in ("DATABASE_URL", "REDIS_URL", "SEARCH_URL"):
    environment.pop(name, None)
command = ["uv", "run", "--locked", "pytest", "tests/integration/test_r03_cursor_persistence.py",
    "tests/integration/test_r03_cursor_review_fixes.py", "tests/integration/test_r03_jobs_pg.py",
    "tests/contract/test_r01_quality_checks.py", "-q", "--no-cov", f"--junitxml={RUN / (label + '.xml')}"]
completed = subprocess.run(command, cwd=ROOT / "backend", env=environment,
    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
output = completed.stdout + completed.stderr
for secret in (database_url, source_url.password):
    if secret:
        output = output.replace(secret, "[REDACTED]")
(RUN / (label + ".log")).write_text(output, encoding="utf-8")
receipt.write_text(json.dumps({"started_at": started,
    "ended_at": datetime.now(clock).isoformat(timespec="seconds"), "command": command,
    "cwd": str(ROOT / "backend"), "exit_code": completed.returncode, "database": database,
    "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
    "uncommitted_files": ["test_r03_cursor_persistence.py", "test_r03_jobs_pg.py", "test_r01_quality_checks.py"]}, indent=2))
print(json.dumps(output[-1800:]))
raise SystemExit(completed.returncode)
