"""Serial owned PostgreSQL checks with secret capture and explicit post-process release."""

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
PYTHON = Path("D:/dianzi/backend/.venv/Scripts/python.exe")
RUN_ID = "r11_int_rev1_fix1_20261016"
DATABASE = "test_dianzi_" + RUN_ID
PWSH = "C:/Users/yinha/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/powershell/pwsh.exe"


def now():
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def read_reference():
    assert datetime.now(ZoneInfo("Asia/Shanghai")) < datetime.fromisoformat("2026-10-17T21:49:15+08:00")
    result = subprocess.run([PWSH, "-NoProfile", "-NonInteractive", "-Command",
        "(Get-Content -LiteralPath 'D:/dianzi-private/test-runtime-resource-reference-20261016.dpapi' -Raw).Trim() | ConvertTo-SecureString | ConvertFrom-SecureString -AsPlainText"],
        capture_output=True, timeout=15, check=False)
    if result.returncode:
        raise RuntimeError("owned_reference_decode_failed")
    url = make_url(json.loads(result.stdout)["TEST_DATABASE_URL"])
    assert (url.host, url.port, url.database) == ("127.0.0.1", 25432, "test_dianzi_r01_20261014")
    assert url.username.startswith("test_")
    return url


def owned_environment(mode):
    environment = os.environ.copy()
    for name in list(environment):
        if name.endswith("API_KEY") or name in {"DATABASE_URL", "REDIS_URL", "OPENSEARCH_URL"}:
            environment.pop(name)
    environment.update(PYTHONPATH=os.pathsep.join([str(ROOT / "backend/src"), str(RUN), str(ROOT / "backend/tests/integration")]),
                       PYTHONIOENCODING="utf-8", APP_ENV="test", DATA_MODE="fixture")
    if mode == "local":
        return environment, []
    source = read_reference()
    database = DATABASE + ("_mig" if mode == "migrations" else "")
    target = source.set(database=database)
    marker = RUN / (mode + "_owned_database.json")
    engine = create_engine(source, isolation_level="AUTOCOMMIT", hide_parameters=True, poolclass=NullPool)
    with engine.connect() as connection:
        exists = connection.scalar(text("SELECT 1 FROM pg_database WHERE datname=:name"), {"name": database})
        if exists:
            assert marker.exists() and json.loads(marker.read_text())["database"] == database
        else:
            assert database.startswith("test_") and len(database) <= 63
            connection.exec_driver_sql('CREATE DATABASE "' + database + '"')
            marker.write_text(json.dumps({"database": database, "created_at": now(), "run_id": RUN_ID}) + "\n")
    engine.dispose()
    engine = create_engine(target, hide_parameters=True, poolclass=NullPool)
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS vector")
        receipt = {"database": database, "run_id": RUN_ID, "server_version": connection.scalar(text("SHOW server_version")),
                   "vector_version": connection.scalar(text("SELECT extversion FROM pg_extension WHERE extname='vector'")),
                   "expires_at": "2026-10-17T21:49:15+08:00", "fixture_engines": "NullPool", "synthetic_fixture": True}
    engine.dispose()
    (RUN / (mode + "_resource_receipt.json")).write_text(json.dumps(receipt, indent=2) + "\n")
    environment.update(TEST_DATABASE_URL=target.render_as_string(hide_password=False), DIANZI_TEST_RUN_ID=RUN_ID,
                       DIANZI_TEST_DB_KIND=mode, R11_FORWARD_EVIDENCE_DIR=str(RUN), R12_OPENSEARCH_URL="http://127.0.0.1:29200",
                       R05_SEMANTIC_CACHE="C:/Users/yinha/.codex/cache/dianzi/r05-semantic-runtime")
    return environment, [source.render_as_string(hide_password=False), target.render_as_string(hide_password=False), source.password]


def main():
    mode, label, *arguments = sys.argv[1:]
    assert mode in {"local", "pg", "migrations"}
    assert not (RUN / (label + ".json")).exists()
    environment, secrets = owned_environment(mode)
    argv = [str(PYTHON), *arguments]
    started = now()
    completed = subprocess.run(argv, cwd=ROOT / "backend", env=environment, capture_output=True,
                               text=True, encoding="utf-8", errors="replace", timeout=360)
    remaining = None
    if mode != "local":
        engine = create_engine(environment["TEST_DATABASE_URL"], hide_parameters=True, poolclass=NullPool)
        with engine.connect() as connection:
            remaining = connection.scalar(text("SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid()"))
        engine.dispose()
    output = completed.stdout + completed.stderr
    for value in secrets:
        if value:
            output = output.replace(value, "[redacted test credential]")
    (RUN / (label + ".log")).write_text(output, encoding="utf-8", newline="\n")
    leaks = []
    for path in RUN.rglob("*"):
        if path.is_file() and not {"__pycache__", "mypy-cache"}.intersection(path.parts):
            if any(value and value.encode() in path.read_bytes() for value in secrets):
                leaks.append(str(path.relative_to(RUN)))
    receipt = {"argv": argv, "cwd": str(ROOT / "backend"), "started_at": started, "ended_at": now(), "exit_code": completed.returncode,
               "owned_database_connections_after_child_exit": remaining,
               "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
               "tree": subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], cwd=ROOT, text=True).strip(),
               "exact_secret_scan_matches": leaks, "output_sha256": hashlib.sha256(output.encode()).hexdigest()}
    (RUN / (label + ".json")).write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"label": label, "exit_code": completed.returncode, "exact_secret_matches": len(leaks), "own_connections_after": remaining}))
    assert not leaks
    assert remaining in {None, 0}, "owned test connections did not release"
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
