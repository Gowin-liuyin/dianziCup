"""Record each new SQLAlchemy backend and apply the existing failure redaction hook."""

import inspect
import json
import os
from pathlib import Path

import pytest
from sqlalchemy import event
from sqlalchemy.engine import Engine
from tests.conftest import (
    isolated_test_database_url,
    pytest_configure,
    pytest_runtest_makereport,
    register_sensitive_failure_value,
)

RUN = Path(__file__).parent
ROOT = RUN.parents[2]
PHASE = "pytest_import"


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item):
    global PHASE
    PHASE = item.nodeid


@event.listens_for(Engine, "connect")
def record_backend(database_connection, connection_record):
    callers = []
    for frame in inspect.stack(context=0):
        try:
            relative = Path(frame.filename).resolve().relative_to(ROOT)
        except ValueError:
            continue
        if relative.parts[0] in {"backend", "reports"}:
            callers.append({"path": str(relative).replace("\\", "/"), "function": frame.function, "line": frame.lineno})
        if len(callers) >= 8:
            break
    with database_connection.cursor() as cursor:
        cursor.execute("SELECT pg_backend_pid(),current_database(),current_user,(SELECT backend_start::text FROM pg_stat_activity WHERE pid=pg_backend_pid())")
        pid, database, username, birth = cursor.fetchone()
    database_connection.rollback()
    label = os.environ.get("R06_MODE_BACKEND_LOG_LABEL", "pg_backend_creation.jsonl")
    if label not in {"pg_backend_creation.jsonl", "recheck_pg_backend_creation.jsonl"}:
        raise ValueError("backend journal label is outside this review")
    with (RUN / label).open("a", encoding="utf-8") as output:
        output.write(json.dumps({"backend_pid": pid, "backend_birth": birth, "database": database, "username": username, "phase": PHASE, "creating_allowlisted_caller": callers, "dsn_logged": False}) + "\n")
