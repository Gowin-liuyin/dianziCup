"""独占合成测试库和内存连接配置；每次运行保留独立证据，不覆盖旧输出。"""

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
RUN_ID = "r11_sbom_locator_fix1_20261016"
DATABASE = "test_dianzi_" + RUN_ID
PWSH = (
    "C:/Users/yinha/.cache/codex-runtimes/codex-primary-runtime/"
    "dependencies/native/powershell/pwsh.exe"
)


def now():
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def read_test_reference():
    assert datetime.now(ZoneInfo("Asia/Shanghai")) < datetime.fromisoformat(
        "2026-10-17T21:49:15+08:00"
    )
    captured = subprocess.run(
        [
            PWSH,
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "(Get-Content -LiteralPath "
            "'D:/dianzi-private/test-runtime-resource-reference-20261016.dpapi' -Raw).Trim() "
            "| ConvertTo-SecureString | ConvertFrom-SecureString -AsPlainText",
        ],
        capture_output=True,
        timeout=15,
        check=False,
    )
    if captured.returncode:
        raise RuntimeError("owned_reference_decode_failed")
    source = make_url(json.loads(captured.stdout)["TEST_DATABASE_URL"])
    assert (source.host, source.port, source.database) == (
        "127.0.0.1",
        25432,
        "test_dianzi_r01_20261014",
    )
    assert source.username.startswith("test_")
    return source


def owned_environment(migrations=False):
    source = read_test_reference()
    database = DATABASE + "_mig" if migrations else DATABASE
    target = source.set(database=database)
    marker = RUN / ("owned_database_migrations.json" if migrations else "owned_database.json")
    engine = create_engine(source, isolation_level="AUTOCOMMIT", hide_parameters=True)
    with engine.connect() as connection:
        exists = connection.scalar(
            text("SELECT 1 FROM pg_database WHERE datname=:name"), {"name": database}
        )
        if exists:
            assert marker.exists() and json.loads(marker.read_text())["database"] == database
        else:
            assert len(database) <= 63 and database.startswith("test_")
            connection.exec_driver_sql('CREATE DATABASE "' + database + '"')
            marker.write_text(
                json.dumps({"database": database, "created_at": now(), "run_id": RUN_ID}) + "\n"
            )
    engine.dispose()
    engine = create_engine(target, hide_parameters=True)
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS vector")
        resource = {
            "database": database,
            "run_id": RUN_ID,
            "server_version": connection.scalar(text("SHOW server_version")),
            "vector_version": connection.scalar(
                text("SELECT extversion FROM pg_extension WHERE extname='vector'")
            ),
            "expires_at": "2026-10-17T21:49:15+08:00",
            "synthetic_fixture": True,
        }
    engine.dispose()
    resource_path = RUN / (
        "migration_resource_receipt.json" if migrations else "resource_receipt.json"
    )
    resource_path.write_text(json.dumps(resource, indent=2) + "\n")
    environment = os.environ.copy()
    for name in list(environment):
        if name.endswith("API_KEY") or name in {"DATABASE_URL", "REDIS_URL", "OPENSEARCH_URL"}:
            environment.pop(name)
    environment.update(
        TEST_DATABASE_URL=target.render_as_string(hide_password=False),
        DIANZI_TEST_RUN_ID=RUN_ID,
        APP_ENV="test",
        DATA_MODE="fixture",
        R11_FORWARD_EVIDENCE_DIR=str(RUN),
        R12_OPENSEARCH_URL="http://127.0.0.1:29200",
        R05_SEMANTIC_CACHE="C:/Users/yinha/.codex/cache/dianzi/r05-semantic-runtime",
        DIANZI_TEST_DB_KIND="migrations" if migrations else "api",
    )
    return (
        environment,
        [
            source.render_as_string(hide_password=False),
            target.render_as_string(hide_password=False),
            source.password,
        ],
        source.username,
    )


def main():
    mode, label, *arguments = sys.argv[1:]
    assert mode in {"local", "pg", "migrations"} and not (RUN / (label + ".json")).exists()
    environment, secrets, username = (
        owned_environment(mode == "migrations")
        if mode != "local"
        else (os.environ.copy(), [], None)
    )
    environment.update(
        PYTHONPATH=os.pathsep.join(
            [str(ROOT / "backend/src"), str(RUN), str(ROOT / "backend/tests/integration")]
        ),
        PYTHONIOENCODING="utf-8",
    )
    argv = [str(PYTHON), *arguments]
    started = now()
    completed = subprocess.run(
        argv,
        cwd=ROOT / "backend",
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=360,
    )
    remaining_connections = None
    if mode != "local":
        engine = create_engine(
            environment["TEST_DATABASE_URL"], hide_parameters=True, poolclass=NullPool
        )
        with engine.connect() as connection:
            remaining_connections = connection.scalar(
                text(
                    "SELECT count(*) FROM pg_stat_activity "
                    "WHERE datname=current_database() AND pid<>pg_backend_pid()"
                )
            )
        engine.dispose()
    output = completed.stdout + completed.stderr
    for secret in secrets:
        if secret:
            output = output.replace(secret, "[redacted test credential]")
    (RUN / (label + ".log")).write_text(output, encoding="utf-8", newline="\n")
    leaks, username_matches = [], []
    for path in RUN.rglob("*"):
        if path.is_file() and "__pycache__" not in path.parts:
            content = path.read_bytes()
            if any(secret and secret.encode() in content for secret in secrets):
                leaks.append(str(path.relative_to(RUN)))
            if username and username.encode() in content:
                username_matches.append(
                    {
                        "path": str(path.relative_to(RUN)),
                        "count": content.count(username.encode()),
                        "file_sha256": hashlib.sha256(content).hexdigest(),
                        "classification": "requires_lexical_review",
                    }
                )
    receipt = {
        "argv": argv,
        "cwd": str(ROOT / "backend"),
        "started_at": started,
        "ended_at": now(),
        "exit_code": completed.returncode,
        "owned_database_connections_after_child_exit": remaining_connections,
        "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "tree": subprocess.check_output(
            ["git", "rev-parse", "HEAD^{tree}"], cwd=ROOT, text=True
        ).strip(),
        "exact_secret_scan_matches": leaks,
        "username_lexical_matches": username_matches,
        "output_sha256": hashlib.sha256(output.encode()).hexdigest(),
    }
    (RUN / (label + ".json")).write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "label": label,
                "exit_code": completed.returncode,
                "exact_secret_scan_count": len(leaks),
                "username_match_files": len(username_matches),
            }
        ),
        flush=True,
    )
    if leaks:
        raise RuntimeError("exact_secret_scan_failed")
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
