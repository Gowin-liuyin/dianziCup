"""Capture bounded author checks without recording private connection values."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
RUN_ID = "r06_catalog_r07_cvss_fix_20261016"
DATABASE = "test_dianzi_" + RUN_ID
SOURCE = "backend/src/ai_intel/enrichment/signals.py"


def now():
    return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run(label, argv, cwd=ROOT, pg=False):
    started = now()
    environment = dict(os.environ)
    for name in ("TEST_DATABASE_URL", "TEST_REDIS_URL", "DIANZI_TEST_RUN_ID"):
        environment.pop(name, None)
    environment.update(
        PYTHONIOENCODING="utf-8",
        PYTHONPATH=os.pathsep.join(
            str(ROOT / path)
            for path in ("backend/src", "backend", "backend/tests/unit", "backend/tests/integration")
        ),
    )
    sensitive = []
    if pg:
        from sqlalchemy import create_engine, text
        from sqlalchemy.engine import make_url

        private = subprocess.run(
            ["wsl.exe", "-d", "Ubuntu-22.04", "-u", "root", "--exec", "cat",
             "/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json"],
            capture_output=True, check=True,
        )
        url = make_url(json.loads(private.stdout)["TEST_DATABASE_URL"])
        assert url.host in {"127.0.0.1", "localhost"} and url.database.startswith("test_dianzi_")
        assert url.username.startswith("test_") and url.port != 5432
        sensitive = [url.render_as_string(hide_password=False), str(url.password)]
        base = create_engine(url, isolation_level="AUTOCOMMIT", connect_args={"connect_timeout": 5})
        try:
            with base.connect() as connection:
                if not connection.scalar(text("SELECT 1 FROM pg_database WHERE datname=:name"), {"name": DATABASE}):
                    connection.execute(text('CREATE DATABASE "' + DATABASE + '"'))
        finally:
            base.dispose()
        environment.update(TEST_DATABASE_URL=url.set(database=DATABASE).render_as_string(hide_password=False), DIANZI_TEST_RUN_ID=RUN_ID)
        sensitive.append(environment["TEST_DATABASE_URL"])
    before = hashlib.sha256((ROOT / SOURCE).read_bytes()).hexdigest()
    result = subprocess.run(argv, cwd=cwd, env=environment, capture_output=True, timeout=600)
    output = result.stdout + result.stderr
    for value in sensitive:
        output = output.replace(value.encode(), b"[redacted test credential]")
    (RUN / (label + ".log")).write_bytes(output)
    counts = None
    xml_path = RUN / (label + ".xml")
    if xml_path.exists():
        content = xml_path.read_bytes()
        for value in sensitive:
            content = content.replace(value.encode(), b"[redacted test credential]")
        xml_path.write_bytes(content)
        cases = ET.fromstring(content).findall(".//testcase")
        counts = {"tests": len(cases), "failures": sum(c.find("failure") is not None for c in cases), "errors": sum(c.find("error") is not None for c in cases), "skipped": sum(c.find("skipped") is not None for c in cases)}
    write_json(RUN / (label + ".command.json"), {
        "argv": argv, "cwd": str(cwd), "started_at": started, "ended_at": now(),
        "exit_code": result.returncode, "counts": counts,
        "head": git("rev-parse", "HEAD").decode().strip(),
        "source_sha256_before": before,
        "source_sha256_after": hashlib.sha256((ROOT / SOURCE).read_bytes()).hexdigest(),
        "database": DATABASE if pg else None, "run_id": RUN_ID if pg else None,
        "new_external_source_model_provider_asset_calls": 0,
    })
    print(json.dumps({"label": label, "exit_code": result.returncode, "counts": counts}))
    return result.returncode


if __name__ == "__main__":
    label, mode, *arguments = sys.argv[1:]
    if mode == "cbm":
        prefix = ["wsl.exe", "-d", "Ubuntu-22.04", "-u", "root", "--", "env",
                  "XDG_CACHE_HOME=/tmp/dianzi-cbm-r07-cvss-authority-scope-fix-20261016",
                  "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp", "cli", "--json"]
        raise SystemExit(run(label, prefix + arguments))
    if mode in {"test", "pg"}:
        argv = [sys.executable, "-m", "pytest", *arguments, "-o", "addopts=", "-q", "--junitxml=" + str(RUN / (label + ".xml"))]
        raise SystemExit(run(label, argv, ROOT / "backend", pg=mode == "pg"))
    raise SystemExit(run(label, arguments, ROOT / "backend" if mode == "backend" else ROOT))
