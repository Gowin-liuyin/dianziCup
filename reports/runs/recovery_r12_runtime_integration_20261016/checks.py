"""Bounded commands with owned test resources and redaction before any log write."""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
PYTHON = Path("D:/dianzi/backend/.venv/Scripts/python.exe")
RUN_ID = "r12_runtime_20261016"


def now():
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()


def test_url():
    result = subprocess.run(
        [
            "C:/Users/yinha/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/powershell/pwsh.exe",
            "-NoProfile",
            "-Command",
            "$r12Protected=Get-Content -LiteralPath "
            "'D:/dianzi-private/test-runtime-resource-reference-20261016.dpapi' -Raw; "
            "$r12Clear=$r12Protected | ConvertTo-SecureString | "
            "ConvertFrom-SecureString -AsPlainText; "
            "[Console]::Write($r12Clear)",
        ],
        capture_output=True,
        timeout=15,
        check=True,
    )
    original = make_url(json.loads(result.stdout)["TEST_DATABASE_URL"])
    if (original.host, original.port, original.database) != (
        "127.0.0.1",
        25432,
        "test_dianzi_r01_20261014",
    ) or not original.username.startswith("test_"):
        raise RuntimeError("owned resource identity rejected")
    configured = original.set(database="test_dianzi_" + RUN_ID)
    marker = RUN / "owned_database.json"
    engine = create_engine(original, isolation_level="AUTOCOMMIT", hide_parameters=True)
    try:
        with engine.connect() as connection:
            exists = connection.scalar(
                text("SELECT 1 FROM pg_database WHERE datname=:name"),
                {"name": configured.database},
            )
            if exists:
                if not marker.exists():
                    raise RuntimeError("existing database without this run ownership marker")
                assert json.loads(marker.read_text())["database"] == configured.database
            else:
                assert configured.database == "test_dianzi_" + RUN_ID
                connection.exec_driver_sql('CREATE DATABASE "' + configured.database + '"')
                marker.write_text(
                    json.dumps({"database": configured.database, "created_at": now()}) + "\n"
                )
    finally:
        engine.dispose()
    return configured


def execute(label, arguments, *, services=False):
    environment = os.environ.copy()
    environment.update(PYTHONPATH=str(ROOT / "backend/src"), PYTHONIOENCODING="utf-8")
    credentials = []
    if services:
        configured = test_url()
        database_url = configured.render_as_string(hide_password=False)
        credentials = [database_url, configured.password]
        environment.update(
            TEST_DATABASE_URL=database_url,
            DIANZI_TEST_RUN_ID=RUN_ID,
            DIANZI_ENV="test",
            R12_OPENSEARCH_URL="http://127.0.0.1:29200",
            R05_SEMANTIC_CACHE="C:/Users/yinha/.codex/cache/dianzi/r05-semantic-runtime",
            R12_EVIDENCE_DIR=str(RUN / "synthetic_source_blobs"),
        )
    argv = [str(PYTHON), *arguments]
    started = now()
    result = subprocess.run(
        argv,
        cwd=ROOT / "backend",
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=240,
    )
    combined = result.stdout + result.stderr
    for credential in credentials:
        if credential:
            combined = combined.replace(credential, "[redacted test credential]")
    (RUN / (label + ".log")).write_text(combined, encoding="utf-8", newline="\n")
    receipt = {
        "argv": argv,
        "cwd": str(ROOT / "backend"),
        "started_at": started,
        "ended_at": now(),
        "exit_code": result.returncode,
        "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
    }
    (RUN / (label + ".json")).write_text(
        json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps({"label": label, "exit_code": result.returncode}), flush=True)
    return result.returncode


if __name__ == "__main__":
    label, *arguments = sys.argv[1:]
    services = "--services" in arguments
    if services:
        arguments.remove("--services")
    raise SystemExit(execute(label, arguments, services=services))
