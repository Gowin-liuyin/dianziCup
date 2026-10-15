"""Check the integrated default factory and the original R07 transaction regressions."""

import json
import os
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
ENV = dict(os.environ, PYTHONIOENCODING="utf8", PYTHONPATH=str(ROOT / "backend/src"))


def record(name, args, environment=ENV, timeout=240):
    started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
    argv = [str(ROOT / "backend/.venv/Scripts/python.exe"), *args]
    with (RUN / (name + ".log")).open("xb") as output:
        result = subprocess.run(argv, cwd=ROOT / "backend", env=environment, stdout=output, stderr=subprocess.STDOUT, timeout=timeout)
    receipt = {"started_at": started, "ended_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"), "cwd": str(ROOT / "backend"), "argv": argv, "exit_code": result.returncode, "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(), "state": "post-5f factory reader wiring before final freeze", "paid_model_provider_source_wire_calls": 0}
    if (RUN / (name + ".xml")).exists():
        suites = ET.parse(RUN / (name + ".xml")).getroot().findall("testsuite")
        receipt["junit"] = {key: sum(int(suite.attrib.get(key, 0)) for suite in suites) for key in ("tests", "failures", "errors", "skipped")}
    (RUN / (name + ".json")).write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"name": name, "exit_code": result.returncode, "junit": receipt.get("junit")}))
    if result.returncode:
        raise SystemExit(result.returncode)


record("default_entry_ruff", ["-m", "ruff", "check", "src/ai_intel", "tests/integration/test_r11_default_readers_pg.py", "tests/integration/test_r07_enrichment_api_pg.py"])
record("default_entry_format", ["-m", "ruff", "format", "--check", "src/ai_intel", "tests/integration/test_r11_default_readers_pg.py", "tests/integration/test_r07_enrichment_api_pg.py"])
record("default_entry_mypy", ["-m", "mypy", "src/ai_intel"])
private = subprocess.run(["wsl.exe", "-d", "Ubuntu-22.04", "-u", "root", "--exec", "cat", "/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json"], capture_output=True, check=True)
url = make_url(json.loads(private.stdout)["TEST_DATABASE_URL"])
assert url.host in {"localhost", "127.0.0.1"} and url.port == 25432
run_id = "r07_execution_api_20261016"
pg_env = dict(ENV, DIANZI_TEST_RUN_ID=run_id, TEST_DATABASE_URL=url.set(database="test_dianzi_" + run_id).render_as_string(hide_password=False))
record("default_entry_pg", ["-m", "pytest", "tests/integration/test_r07_job_execution_pg.py", "tests/integration/test_r07_enrichment_api_pg.py", "tests/integration/test_r11_default_readers_pg.py", "--no-cov", "-q", "--junitxml=" + str(RUN / "default_entry_pg.xml")], pg_env)
record("default_entry_contract", ["-m", "pytest", "tests/contract/test_r07_enrichment_api_response.py", "tests/contract/test_r07_enrichment_runtime_policy.py", "tests/unit/test_r01_worker_configuration.py", "tests/unit/test_r01_runtime_settings.py", "tests/unit/test_r04_source_jobs.py", "--no-cov", "-q", "--junitxml=" + str(RUN / "default_entry_contract.xml")])
