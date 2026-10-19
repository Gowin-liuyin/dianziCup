"""Create only the named test database and run inspected UUID-schema fixtures."""

import json
import os
from pathlib import Path
import subprocess
import sys

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
TARGET = "test_dianzi_r06_catalog_gc_8a_20261016"
RUN_ID = "r06_catalog_gc_8a_20261016"
captured = subprocess.check_output([
    "wsl.exe", "-d", "Ubuntu-22.04", "-u", "root", "--", "cat",
    "/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json",
], text=True, timeout=15)
configuration = json.loads(captured)
url = make_url(configuration["TEST_DATABASE_URL"])
assert url.database == configuration["postgres_database"] and url.database.startswith("test_")
dedicated = url.set(database=TARGET)
environment = dict(os.environ, PYTHONUTF8="1", TEST_DATABASE_URL=dedicated.render_as_string(hide_password=False), DIANZI_TEST_RUN_ID=RUN_ID)
environment.pop("TEST_REDIS_URL", None)
sys.path.insert(0, str(ROOT))
from scripts.dev import require_isolated_test_database

require_isolated_test_database(environment)
admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT", connect_args={"connect_timeout": 5})
with admin.connect() as connection:
    actual_database, actual_user = connection.execute(text("SELECT current_database(), current_user")).one()
    assert actual_database == "postgres" and actual_user == url.username
    present = connection.scalar(text("SELECT EXISTS(SELECT 1 FROM pg_database WHERE datname=:name)"), {"name": TARGET})
    assert not present, "dedicated validation database already exists"
    connection.execute(text("CREATE DATABASE test_dianzi_r06_catalog_gc_8a_20261016"))
admin.dispose()
engine = create_engine(dedicated, connect_args={"connect_timeout": 5})
with engine.connect() as connection:
    actual_database, actual_user = connection.execute(text("SELECT current_database(), current_user")).one()
    assert actual_database == TARGET and actual_user == url.username
    before = inspect(connection).get_table_names(schema="public")
    schemas_before = connection.scalars(text("SELECT schema_name FROM information_schema.schemata WHERE schema_name LIKE 'test_%' ORDER BY schema_name")).all()
    assert before == [] and schemas_before == []
(RUN / "pg_isolation_before.json").write_text(json.dumps({"database": TARGET, "run_id": RUN_ID, "created": True, "identity_matches": True, "public_tables": before, "test_schemas": schemas_before}, indent=2), encoding="utf-8")
files = [
    "tests/integration/test_r06_source_worker_pg.py",
    "tests/integration/test_r06_failed_response_persistence_pg.py",
    "tests/integration/test_r06_catalog_documents_pg.py",
    "tests/integration/test_r04_source_jobs_pg.py",
    "tests/integration/test_r07_signal_claim_values_pg.py",
    "tests/integration/test_r07_literature_target_scope_pg.py",
]
argv = [sys.executable, str(RUN / "run_command.py"), "--cwd", str(ROOT / "backend"), "pg_selected_actual", "--", sys.executable, "-m", "pytest", *files, "--no-cov", "-q", "--tb=short", "-p", "no:cacheprovider", "--basetemp", str(RUN / "pg_pytest_tmp"), "--junitxml", str(RUN / "pg_selected.xml")]
result = subprocess.run(argv, env=environment, capture_output=True, check=False)
secrets = [environment["TEST_DATABASE_URL"], url.password]
for suffix in ("stdout.log", "stderr.log", "xml"):
    path = RUN / ("pg_selected_actual." + suffix) if suffix != "xml" else RUN / "pg_selected.xml"
    if path.exists():
        output = path.read_bytes()
        for secret in secrets:
            if secret:
                output = output.replace(secret.encode(), b"[redacted test credential]")
        path.write_bytes(output)
with engine.connect() as connection:
    after = inspect(connection).get_table_names(schema="public")
    schemas_after = connection.scalars(text("SELECT schema_name FROM information_schema.schemata WHERE schema_name LIKE 'test_%' ORDER BY schema_name")).all()
assert after == before == [] and schemas_after == schemas_before == []
engine.dispose()
(RUN / "pg_isolation_after.json").write_text(json.dumps({"database": TARGET, "run_id": RUN_ID, "public_tables": after, "test_schemas": schemas_after, "child_exit_code": result.returncode, "dsn_in_argv": False}, indent=2), encoding="utf-8")
print(json.dumps({"child_exit_code": result.returncode, "database": TARGET, "public_unchanged": True, "fixture_schemas_cleaned": True}))
raise SystemExit(result.returncode)
