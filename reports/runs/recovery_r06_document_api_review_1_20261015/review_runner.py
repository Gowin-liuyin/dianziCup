"""Capture review commands without publishing test database credentials."""
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
PYTHON = ROOT / "backend/.venv/Scripts/python.exe"
RUN_ID = "r06_catalog_document_review_20261015"


def now():
    return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")


def pg_environment(environment):
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url

    private = subprocess.run(
        ["wsl.exe", "-d", "Ubuntu-22.04", "-u", "root", "--exec", "cat",
         "/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json"],
        capture_output=True, check=True,
    )
    url = make_url(json.loads(private.stdout)["TEST_DATABASE_URL"])
    assert url.host in {"127.0.0.1", "localhost"}
    assert url.database.startswith("test_dianzi_") and "r04" not in url.database
    database = "test_dianzi_" + RUN_ID
    base = create_engine(url, isolation_level="AUTOCOMMIT")
    with base.connect() as connection:
        if not connection.scalar(text("SELECT 1 FROM pg_database WHERE datname=:name"), {"name": database}):
            connection.execute(text('CREATE DATABASE "' + database + '"'))
    base.dispose()
    environment["TEST_DATABASE_URL"] = url.set(database=database).render_as_string(hide_password=False)
    environment["DIANZI_TEST_RUN_ID"] = RUN_ID


def snapshot(environment):
    from sqlalchemy import create_engine, text

    engine = create_engine(environment["TEST_DATABASE_URL"])
    with engine.connect() as connection:
        tables = list(connection.scalars(text(
            "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"
        )))
        counts = {name: connection.scalar(text('SELECT count(*) FROM public."' + name + '"')) for name in tables}
        versions = list(connection.scalars(text("SELECT version_num FROM public.alembic_version ORDER BY version_num"))) if "alembic_version" in tables else []
    engine.dispose()
    return {"database": "test_dianzi_" + RUN_ID, "public_counts": counts, "public_versions": versions}


def main():
    mode = sys.argv[1]
    label = sys.argv[2] if len(sys.argv) > 2 else mode
    environment = dict(os.environ)
    for key in ("TEST_DATABASE_URL", "DIANZI_TEST_RUN_ID", "PYTHONPATH", "VIRTUAL_ENV"):
        environment.pop(key, None)
    options = {
        "sync": ["uv", "sync", "--frozen", "--extra", "semantic"],
        "pure": [str(PYTHON), "-m", "pytest", "tests/unit", "tests/contract", "tests/security", "-m", "not real_pg", "-q"],
        "pg": [str(PYTHON), "-m", "pytest", "tests/integration/test_r06_document_api_pg.py", "--no-cov", "-q"],
        "probe": [str(PYTHON), "-m", "pytest", str(RUN / "test_independent_probes.py"), "--no-cov", "-q", "--import-mode=importlib", "-p", "conftest"],
        "ruff": [str(PYTHON), "-m", "ruff", "check", "src", "tests"],
        "format": [str(PYTHON), "-m", "ruff", "format", "--check", "src", "tests"],
        "mypy": [str(PYTHON), "-m", "mypy", "src"],
        "diff": ["git", "diff", "--check", "71e852ce4be147d30aa1bc824bf18afda99fb332", "49ee33f6a95099be619a59ff47c621713a089137"],
    }
    if mode in {"pg", "probe"}:
        pg_environment(environment)
        before = snapshot(environment)
        (RUN / (label + "_public_before.json")).write_text(json.dumps(before, indent=2) + "\n", encoding="utf-8")
    if mode == "probe":
        environment["PYTHONPATH"] = os.pathsep.join([str(ROOT / "backend/tests"), str(ROOT / "backend/tests/integration")])
    argv = options[mode]
    if mode in {"pure", "pg", "probe"}:
        argv += ["--junitxml=" + str(RUN / (label + ".xml"))]
    started = now()
    cwd = ROOT if mode == "diff" else ROOT / "backend"
    with (RUN / (label + ".log")).open("wb") as output:
        result = subprocess.run(argv, cwd=cwd, env=environment, stdout=output, stderr=subprocess.STDOUT, timeout=600, check=False)
    ended = now()
    (RUN / (label + ".command.json")).write_text(json.dumps({
        "argv": argv, "cwd": str(cwd), "started_at": started, "ended_at": ended,
        "exit_code": result.returncode,
        "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "product_sha": "49ee33f6a95099be619a59ff47c621713a089137",
        "database_environment": "absent" if mode not in {"pg", "probe"} else "private DSN; dedicated database; UUID schema fixture",
    }, indent=2) + "\n", encoding="utf-8")
    if mode in {"pg", "probe"}:
        after = snapshot(environment)
        (RUN / (label + "_public_after.json")).write_text(json.dumps(after, indent=2) + "\n", encoding="utf-8")
        assert before == after, "public schema changed"
    print(json.dumps({"mode": mode, "exit_code": result.returncode, "started_at": started, "ended_at": ended}))
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
