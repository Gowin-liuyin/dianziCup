"""Record static checks, related regressions and real isolated PG with no external calls."""

import json
import os
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
PYTHON = str(ROOT / "backend/.venv/Scripts/python.exe")
ENV = dict(os.environ, PYTHONIOENCODING="utf8", PYTHONPATH=str(ROOT / "backend/src"))
SOURCE_FILES = [
    "src/ai_intel/api/app.py", "src/ai_intel/api/source_routes.py",
    "src/ai_intel/api/enrichment_contracts.py", "src/ai_intel/api/enrichment_routes.py",
    "src/ai_intel/api/job_routes.py", "src/ai_intel/enrichment/runtime_policy.py",
    "src/ai_intel/infrastructure/settings.py", "src/ai_intel/workers/runtime.py",
    "tests/contract/test_r07_enrichment_api_response.py",
    "tests/contract/test_r07_enrichment_runtime_policy.py",
    "tests/integration/test_r07_enrichment_api_pg.py",
]


def now():
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def record(name, arguments, environment=ENV, timeout=180):
    started = now()
    argv = [PYTHON, *arguments]
    with (RUN / (name + ".log")).open("xb") as output:
        result = subprocess.run(argv, cwd=ROOT / "backend", env=environment, stdout=output, stderr=subprocess.STDOUT, timeout=timeout)
    receipt = {"started_at": started, "ended_at": now(), "cwd": str(ROOT / "backend"), "argv": argv, "exit_code": result.returncode, "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(), "source_state": "root API/worker WIP; final source byte proof at freeze", "product_model_provider_source_wire_calls": 0}
    xml_path = RUN / (name + ".xml")
    if xml_path.exists():
        suites = ET.parse(xml_path).getroot().findall("testsuite")
        receipt["junit"] = {field: sum(int(suite.attrib.get(field, 0)) for suite in suites) for field in ("tests", "failures", "errors", "skipped")}
    (RUN / (name + ".json")).write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"name": name, "exit_code": result.returncode, "junit": receipt.get("junit")}))
    if result.returncode:
        raise SystemExit(result.returncode)


record("api_worker_ruff_final", ["-m", "ruff", "check", *SOURCE_FILES])
record("api_worker_format_final", ["-m", "ruff", "format", "--check", *SOURCE_FILES])
record("api_worker_mypy_final", ["-m", "mypy", "src/ai_intel"])
pure = [
    "tests/unit/test_r07_job_execution_helpers.py", "tests/contract/test_r07_job_execution_views.py",
    "tests/security/test_r07_job_execution_boundaries.py", "tests/contract/test_r07_enrichment_api_response.py",
    "tests/contract/test_r07_enrichment_runtime_policy.py", "tests/contract/test_r07_enrichment_job_request.py",
    "tests/contract/test_r07_enrichment_execution_policy.py", "tests/unit/test_r01_worker_configuration.py",
    "tests/unit/test_r01_application_settings.py", "tests/unit/test_r04_source_jobs.py",
]
record("api_worker_related_final", ["-m", "pytest", *pure, "--no-cov", "-q", "--junitxml=" + str(RUN / "api_worker_related_final.xml")])
private = subprocess.run(["wsl.exe", "-d", "Ubuntu-22.04", "-u", "root", "--exec", "cat", "/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json"], capture_output=True, check=True)
from sqlalchemy.engine import make_url
url = make_url(json.loads(private.stdout)["TEST_DATABASE_URL"])
assert url.host in {"localhost", "127.0.0.1"} and url.port == 25432 and url.database.startswith("test_dianzi_")
pg_environment = dict(ENV, TEST_DATABASE_URL=url.set(database="test_dianzi_r07_execution_api_20261016").render_as_string(hide_password=False), DIANZI_TEST_RUN_ID="r07_execution_api_final_20261016")
pg = ["tests/integration/test_r07_job_execution_pg.py", "tests/integration/test_r07_enrichment_api_pg.py", "tests/integration/test_r07_enrichment_job_metadata_pg.py"]
record("api_worker_combined_pg_final", ["-m", "pytest", *pg, "--no-cov", "-q", "--junitxml=" + str(RUN / "api_worker_combined_pg_final.xml")], pg_environment, 300)
