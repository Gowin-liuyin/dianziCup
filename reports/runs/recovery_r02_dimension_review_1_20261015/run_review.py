"""Freeze the candidate, keep connection secrets in subprocess environment, and save receipts."""

from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import sys
from urllib.parse import unquote, urlsplit

ARTIFACTS = Path(__file__).resolve().parent
WORKTREE = Path(r"C:\Users\yinha\.codex\worktrees\recovery-r02-dimensions-review\dianzi")
BACKEND = WORKTREE / "backend"
PYTHON = Path(r"D:\dianzi\backend\.venv\Scripts\python.exe")
ZONE = dt.timezone(dt.timedelta(hours=8))


def timestamp() -> str:
    return dt.datetime.now(ZONE).isoformat(timespec="seconds")


def run(name: str, command: list[str], env: dict[str, str]) -> int:
    start = timestamp()
    process = subprocess.run(command, cwd=BACKEND, env=env, capture_output=True,
                             text=True, encoding="utf-8", errors="replace")
    output = process.stdout + process.stderr
    connection_url = env.get("TEST_DATABASE_URL", "")
    password = unquote(urlsplit(connection_url).password or "") if connection_url else ""
    for secret in (connection_url, password):
        if secret:
            output = output.replace(secret, "[redacted test connection]")
    (ARTIFACTS / (name + ".log")).write_text(output, encoding="utf-8")
    receipt = {"start": start, "end": timestamp(), "cwd": str(BACKEND),
               "command": command, "exit_code": process.returncode,
               "candidate": "a366c4e5616d8a163ef69431cd2d90e8988b88fa"}
    (ARTIFACTS / (name + ".command.json")).write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    print(name, process.returncode, output[-1800:])
    return process.returncode


def main() -> int:
    mode = sys.argv[1]
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(map(str, (
        BACKEND / "src", BACKEND / "tests", BACKEND / "tests/integration")))
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    if mode in {"scope", "scope_final", "pg", "negative", "negative_final"}:
        secret_process = subprocess.run([
            "wsl", "-u", "root", "--", "cat",
            "/tmp/dianzi-r02_dimensions_20261015/connection.json"
        ], capture_output=True, text=True, encoding="utf-8", check=True)
        connection = json.loads(secret_process.stdout)
        if urlsplit(connection["TEST_DATABASE_URL"]).path != "/test_dianzi_r02_dimensions_20261015":
            raise RuntimeError("unexpected test database scope")
        env.update(connection)
    if mode in {"scope", "scope_final"}:
        code = """import json, os, ai_intel.enrichment.persistence as p
from sqlalchemy import create_engine,text
e=create_engine(os.environ['TEST_DATABASE_URL'],connect_args={'connect_timeout':5})
with e.connect() as c:
 print(json.dumps({'database_scope':list(c.execute(text('select current_database(),current_user')).one()),'migration':c.scalar(text('select version_num from alembic_version')),'candidate_source':p.__file__}))
e.dispose()"""
        return run(mode, [str(PYTHON), "-c", code], env)
    if mode == "unit":
        return run(mode, [str(PYTHON), "-m", "pytest", "tests/unit", "-q",
                         "--junitxml=" + str(ARTIFACTS / "unit.xml")], env)
    if mode == "pg":
        return run(mode, [str(PYTHON), "-m", "pytest",
                         "tests/integration/test_r02_dimension_persistence.py",
                         "tests/integration/test_r02_dimension_migration.py",
                         "tests/integration/test_r02_schema_migration.py", "-q", "--no-cov",
                         "--junitxml=" + str(ARTIFACTS / "pg.xml")], env)
    if mode in {"negative", "negative_final"}:
        return run(mode, [str(PYTHON), "-m", "pytest", str(ARTIFACTS / "test_independent_dimensions.py"),
                         "-q", "-c", str(BACKEND / "pyproject.toml"), "-p", "conftest", "--no-cov",
                         "--junitxml=" + str(ARTIFACTS / (mode + ".xml"))], env)
    if mode == "static":
        results = [run(name, [str(PYTHON), "-m", *args], env) for name, args in (
            ("ruff", ["ruff", "check", "."]),
            ("format", ["ruff", "format", "--check", "."]),
            ("mypy", ["mypy", "src"]),
        )]
        return max(results)
    raise RuntimeError("unknown review mode")


if __name__ == "__main__":
    raise SystemExit(main())
