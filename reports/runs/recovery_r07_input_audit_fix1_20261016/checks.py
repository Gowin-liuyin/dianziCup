"""Run bounded checks with a single DPAPI test resource and redact before recording output."""

import html
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import quote
from xml.etree import ElementTree
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
PYTHON = ROOT / "backend/.venv/Scripts/python.exe"
RUN_ID = "r07_input_audit_fix1_20261016"
DATABASE = "test_dianzi_" + RUN_ID
OWNER = "r07-input-audit-fix1:014de585413c8a82a04d00b1ff2fbd1ff62d733b"


def now():
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def resource_url():
    protected = subprocess.run(["C:/Users/yinha/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/powershell/pwsh.exe", "-NoProfile", "-Command", "$taskProtected=Get-Content -LiteralPath 'D:/dianzi-private/test-runtime-resource-reference-20261016.dpapi' -Raw; $taskClear=$taskProtected | ConvertTo-SecureString | ConvertFrom-SecureString -AsPlainText; [Console]::Write($taskClear)"], capture_output=True, timeout=15, check=True)
    original = make_url(json.loads(protected.stdout)["TEST_DATABASE_URL"])
    assert original.drivername == "postgresql+psycopg"
    assert (original.host, original.port, original.database) == ("127.0.0.1", 25432, "test_dianzi_r01_20261014")
    assert original.username and original.username.startswith("test_") and original.password
    configured = original.set(database=DATABASE)
    marker = RUN / "owned_database.json"
    engine = create_engine(original, isolation_level="AUTOCOMMIT", hide_parameters=True, poolclass=NullPool)
    try:
        with engine.connect() as connection:
            existing = connection.execute(text("SELECT shobj_description(oid,'pg_database') AS owner_marker, pg_get_userbyid(datdba) AS owner FROM pg_database WHERE datname=:name"), {"name": DATABASE}).mappings().one_or_none()
            if existing is not None:
                assert marker.exists() and json.loads(marker.read_bytes()) == {"database": DATABASE, "owner": OWNER}
                assert existing["owner_marker"] == OWNER and existing["owner"] == original.username
            else:
                connection.exec_driver_sql('CREATE DATABASE "' + DATABASE + '"')
                connection.exec_driver_sql('COMMENT ON DATABASE "' + DATABASE + "\" IS '" + OWNER + "'")
                marker.write_bytes(json.dumps({"database": DATABASE, "owner": OWNER}, indent=2).encode())
    finally:
        engine.dispose()
    return configured


def execute(label, arguments, *, services):
    environment = os.environ.copy()
    environment.update(PYTHONPATH=os.pathsep.join(str(path) for path in (ROOT / "backend/src", ROOT / "backend/tests", ROOT / "backend/tests/integration", ROOT, RUN)), PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1", DIANZI_ENV="test")
    credentials = []
    if services:
        configured = resource_url()
        database_url = configured.render_as_string(hide_password=False)
        credentials = [database_url, configured.password]
        environment.update(TEST_DATABASE_URL=database_url, DIANZI_TEST_RUN_ID=RUN_ID)
    started = now()
    source = RUN / "baseline_job_service.py" if "baseline_import" in arguments else ROOT / "backend/src/ai_intel/enrichment/job_service.py"
    source_digest = hashlib.sha256(source.read_bytes()).hexdigest()
    argv = [str(PYTHON), *arguments]
    result = subprocess.run(argv, cwd=ROOT / "backend", env=environment, capture_output=True, timeout=360, text=True, encoding="utf-8", errors="replace")
    patterns = {variant for value in credentials if value for variant in (value, html.escape(value), quote(value, safe=""), json.dumps(value)[1:-1])}
    combined = result.stdout + result.stderr
    for value in sorted(patterns, key=len, reverse=True):
        combined = combined.replace(value, "[redacted test credential]")
    xml = RUN / (label + ".xml")
    if xml.exists():
        raw_xml = xml.read_text(encoding="utf-8")
        assert not any(value in raw_xml for value in patterns), "credential found in JUnit; no contents displayed"
    (RUN / (label + ".log")).write_bytes(combined.encode())
    suites = [] if not xml.exists() else list(ElementTree.parse(xml).getroot().iter("testsuite"))
    counts = {name: sum(int(suite.attrib.get(name, "0")) for suite in suites) for name in ("tests", "failures", "errors", "skipped")}
    receipt = {"argv": argv, "cwd": str(ROOT / "backend"), "started_at": started, "ended_at": now(), "exit_code": result.returncode, "counts": counts, "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(), "execution_service_source": str(source), "execution_service_raw_sha256": source_digest, "source_unchanged_during_command": hashlib.sha256(source.read_bytes()).hexdigest() == source_digest, "actual_sensitive_value_scan": {"log_matches": 0, "junit_matches": 0 if xml.exists() else None}, "resource": DATABASE if services else None}
    (RUN / (label + ".json")).write_bytes(json.dumps(receipt, indent=2).encode())
    print(json.dumps({"label": label, "exit_code": result.returncode, "counts": counts}), flush=True)
    return result.returncode


if __name__ == "__main__":
    label, *arguments = sys.argv[1:]
    services = "--services" in arguments
    if services:
        arguments.remove("--services")
    raise SystemExit(execute(label, arguments, services=services))
