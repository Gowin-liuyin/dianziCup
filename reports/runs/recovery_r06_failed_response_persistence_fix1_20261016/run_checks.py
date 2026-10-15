"""Capture only this frozen regression fix; private service configuration stays in memory."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
sys.path.insert(0, str(ROOT))
DATABASE = "test_dianzi_r06_catalog_failure_receipt_fix1_20261016"
RUN_ID = "r06_catalog_failure_receipt_fix1_20261016"
PURE_FILES = [
    "tests/unit/test_r06_failed_response_boundary.py",
    "tests/unit/test_r06_source_worker.py",
    "tests/unit/test_r04_source_jobs.py",
    "tests/unit/test_r04_source_rate_limits.py",
    "tests/unit/test_r06_source_boundary_regressions.py",
    "tests/unit/test_r06_catalog_pages.py",
    "tests/unit/test_r06_feed_parsers.py",
    "tests/unit/test_r06_avid_record_adapter.py",
    "tests/unit/test_r06_github_release_adapter.py",
    "tests/unit/test_r04_source_documents.py",
    "tests/contract/test_r06_archived_feed_replay.py",
    "tests/contract/test_r06_repository_source_samples.py",
]


def private_configuration() -> dict[str, str]:
    captured = subprocess.check_output(
        [
            "wsl",
            "-d",
            "Ubuntu-22.04",
            "-u",
            "root",
            "--",
            "cat",
            "/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json",
        ],
        text=True,
        timeout=10,
    )
    return json.loads(captured)


def run_check(label: str, arguments: list[str], *, pg: bool = False) -> int:
    environment = dict(os.environ, PYTHONUTF8="1")
    for name in ("TEST_DATABASE_URL", "TEST_REDIS_URL", "DIANZI_TEST_RUN_ID"):
        environment.pop(name, None)
    credentials: list[str] = []
    public_before: list[str] | None = None
    public_after: list[str] | None = None
    if pg:
        from scripts.dev import require_isolated_test_database

        configuration = private_configuration()
        configured = make_url(configuration["TEST_DATABASE_URL"])
        assert configured.database == configuration["postgres_database"]
        assert configured.database is not None and configured.database.startswith("test_")
        url = configured.set(database=DATABASE)
        environment.update(
            TEST_DATABASE_URL=url.render_as_string(hide_password=False), DIANZI_TEST_RUN_ID=RUN_ID
        )
        require_isolated_test_database(environment)
        admin = create_engine(
            url.set(database="postgres"),
            isolation_level="AUTOCOMMIT",
            connect_args={"connect_timeout": 5},
        )
        with admin.connect() as connection:
            present = connection.scalar(
                text("SELECT EXISTS (SELECT 1 FROM pg_database WHERE datname=:name)"),
                {"name": DATABASE},
            )
            if not present:
                connection.execute(
                    text("CREATE DATABASE test_dianzi_r06_catalog_failure_receipt_fix1_20261016")
                )
        admin.dispose()
        engine = create_engine(url, connect_args={"connect_timeout": 5})
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT current_database()")) == DATABASE
            public_before = inspect(connection).get_table_names(schema="public")
            assert public_before == []
        engine.dispose()
        credentials = [environment["TEST_DATABASE_URL"], configured.password or ""]
    source_files = [
        ROOT / "backend/tests/integration/test_r06_source_worker_pg.py",
        ROOT / "backend/src/ai_intel/ingestion/source_jobs.py",
        ROOT / "backend/src/ai_intel/ingestion/source_failure_receipts.py",
    ]
    receipt: dict[str, object] = {
        "argv": arguments,
        "cwd": str(ROOT / "backend"),
        "code_sha": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "started_at": datetime.now().astimezone().isoformat(),
        "source_sha256": {
            path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in source_files
        },
    }
    completed = subprocess.run(
        arguments, cwd=ROOT / "backend", env=environment, capture_output=True
    )
    output = completed.stdout + completed.stderr
    for credential in credentials:
        if credential:
            output = output.replace(credential.encode(), b"[redacted]")
    (RUN / (label + ".log")).write_bytes(output)
    if pg:
        with create_engine(url, connect_args={"connect_timeout": 5}).connect() as connection:
            public_after = inspect(connection).get_table_names(schema="public")
        assert public_before == public_after == []
    receipt.update(
        finished_at=datetime.now().astimezone().isoformat(),
        exit_code=completed.returncode,
        database=DATABASE if pg else None,
        public_before=public_before,
        public_after=public_after,
    )
    (RUN / (label + ".json")).write_text(
        json.dumps(receipt, indent=2), encoding="utf-8", newline="\n"
    )
    print(
        json.dumps(
            {"label": label, "exit_code": completed.returncode, "code_sha": receipt["code_sha"]}
        )
    )
    return completed.returncode


if __name__ == "__main__":
    label = sys.argv[1]
    if label == "pure_frozen":
        arguments = [sys.executable, "-m", "pytest", *PURE_FILES]
    elif label.startswith("pg_") or label.startswith("collect_") or label == "isolation_guard":
        arguments = [sys.executable, "-m", "pytest", *sys.argv[2:]]
    else:
        arguments = [sys.executable, "-m", *sys.argv[2:]]
    if "pytest" in arguments:
        arguments += ["--no-cov", "-q", "--tb=short", "--junitxml=" + str(RUN / (label + ".xml"))]
    raise SystemExit(run_check(label, arguments, pg=label.startswith("pg_")))
