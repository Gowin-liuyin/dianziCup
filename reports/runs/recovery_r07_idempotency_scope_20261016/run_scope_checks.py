"""Use private credentials only in memory and collect truthful red/green isolated QA evidence."""

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
ZONE = ZoneInfo("Asia/Shanghai")
PYTHON = ROOT / "backend/.venv/Scripts/python.exe"
BASE = "e61d9d6dd1215c337755d32d112dfe70f13d9e94"


def now():
    return datetime.now(ZONE).isoformat(timespec="seconds")


def prepare_database(environment, name):
    private = json.loads(subprocess.check_output(["wsl.exe", "-d", "Ubuntu-22.04", "-u", "root", "--exec", "cat", "/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json"], stderr=subprocess.PIPE))
    url = make_url(private["TEST_DATABASE_URL"])
    assert url.host in {"127.0.0.1", "localhost"} and url.port == 25432 and url.username.startswith("test_")
    assert name in {"test_dianzi_r07_execution_scope_20261016", "test_dianzi_r07_execution_api_scope_20261016"}
    administrator = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with administrator.connect() as connection:
        if not connection.scalar(text("SELECT 1 FROM pg_database WHERE datname=:name"), {"name": name}):
            connection.execute(text('CREATE DATABASE "' + name + '"'))
    administrator.dispose()
    environment["TEST_DATABASE_URL"] = url.set(database=name).render_as_string(hide_password=False)
    environment["DIANZI_TEST_RUN_ID"] = name.removeprefix("test_dianzi_")
    return private


def main():
    mode = sys.argv[1]
    started = now()
    environment = dict(os.environ, PYTHONIOENCODING="utf8", PYTHONPATH=os.pathsep.join((str(ROOT / "backend/src"), str(ROOT / "backend/tests/integration"), str(ROOT), str(RUN))))
    paths = {
        "unit": ["tests/unit/test_r07_idempotency_namespace.py"],
        "contract": ["tests/contract/test_r07_idempotency_namespace_contract.py"],
        "pg": ["tests/integration/test_r07_idempotency_scope_pg.py"],
        "security": ["tests/security/test_r07_idempotency_scope_security.py"],
        "regression": ["tests/integration/test_r07_job_execution_pg.py", "tests/integration/test_r07_enrichment_api_pg.py", str(RUN / "probes/test_independent_idempotency_scope.py")],
        "red": ["tests/integration/test_r07_job_execution_pg.py", "tests/integration/test_r07_enrichment_api_pg.py", str(RUN / "probes/test_independent_idempotency_scope.py")],
    }
    private = prepare_database(environment, "test_dianzi_r07_execution_api_scope_20261016" if mode in {"red", "regression"} else "test_dianzi_r07_execution_scope_20261016") if mode in {"pg", "security", "red", "regression"} else {}
    tag = mode + "_" + datetime.now(ZONE).strftime("%H%M%S")
    xml_path = RUN / (tag + ".xml")
    plugin = ["-p", "artifact_redirect"] if mode in {"red", "regression"} else []
    if mode == "red":
        plugin += ["-p", "baseline_import"]
    command = [str(PYTHON), "-m", "pytest", "-q", *plugin, *paths[mode], *sys.argv[2:], "--no-cov", "--junitxml=" + str(xml_path)]
    result = subprocess.run(command, cwd=ROOT / "backend", env=environment, capture_output=True, text=True, encoding="utf-8", timeout=300)
    output = result.stdout + result.stderr
    for sensitive in (private.get("TEST_DATABASE_URL"), private.get("postgres_password"), private.get("redis_password"), environment.get("TEST_DATABASE_URL")):
        if sensitive:
            output = output.replace(sensitive, "[redacted private credential]")
    (RUN / (tag + ".log")).write_bytes(output.encode())
    cases = ElementTree.parse(xml_path).findall(".//testcase")
    counts = {"tests": len(cases), "failed": sum(case.find("failure") is not None for case in cases), "errors": sum(case.find("error") is not None for case in cases), "skipped": sum(case.find("skipped") is not None for case in cases)}
    receipt = {"started_at": started, "completed_at": now(), "command": command, "cwd": str(ROOT / "backend"), "exit_code": result.returncode, "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(), "source_state": "baseline module override" if mode == "red" else "owned namespace patch working tree", "external_network_calls": 0, "paid_calls": 0, "fee": "unknown", **counts}
    (RUN / (tag + ".json")).write_bytes(json.dumps(receipt, indent=2).encode())
    print(json.dumps({"mode": mode, "exit_code": result.returncode, **counts}))
    if result.returncode:
        print(output[-6500:])
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
