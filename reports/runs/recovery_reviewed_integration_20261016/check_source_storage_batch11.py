"""Exercise source/storage/worker integration with explicit offline inputs and no external IO."""

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
PYTHON = ROOT / "backend/.venv/Scripts/python.exe"
environment = os.environ.copy()
environment.update({"APP_ENV": "test", "DATA_MODE": "fixture", "DATABASE_URL": "postgresql://test_fixture@127.0.0.1/test_dianzi_unit", "REDIS_URL": "redis://127.0.0.1:26379/15", "SOURCE_POLLING_ENABLED": "false", "ENRICHMENT_GENERATION_ENABLED": "false", "PYTHONIOENCODING": "utf-8", "PYTHONPATH": str(ROOT / "backend/src")})
for name in ("GENERATION_API_KEY", "REVALIDATION_CURSOR_SIGNING_KEY", "FOFA_API_KEY", "HUNTER_API_KEY", "QUAKE_API_KEY", "ZOOMEYE_API_KEY"):
    environment.pop(name, None)
tests = [
    "tests/unit/test_content_store_fd_failure.py", "tests/unit/test_content_store_cleanup_failure.py",
    "tests/unit/test_content_store_descriptor_close_failure.py", "tests/unit/test_content_store_exclusive_publication.py",
    "tests/unit/test_t05_content_store_boundaries.py", "tests/contract/test_t09_document_parsing.py",
    "tests/unit/test_r06_source_data_mode.py", "tests/contract/test_r06_source_data_mode_contract.py",
    "tests/unit/test_r06_default_worker_data_mode.py", "tests/unit/test_r06_source_worker.py",
    "tests/unit/test_r06_source_catalog.py", "tests/unit/test_r06_catalog_pages.py",
    "tests/unit/test_r04_source_jobs.py", "tests/unit/test_r03_jobs_contract.py",
    "tests/unit/test_r01_worker_configuration.py", "tests/unit/test_r16_revalidation_runtime.py",
    "tests/unit/test_r16_default_worker_registration.py", "tests/unit/test_detached_job_executor.py",
    "tests/contract/test_detached_job_executor_contract.py", "tests/unit/test_detached_job_completion_guard.py",
    "tests/contract/test_detached_job_completion_guard_contract.py",
]
sources = ["src/ai_intel/infrastructure/content_store.py", "src/ai_intel/ingestion/catalog_documents.py", "src/ai_intel/ingestion/source_documents.py", "src/ai_intel/ingestion/source_jobs.py", "src/ai_intel/workers/executor.py", "src/ai_intel/workers/runtime.py"]
checks = [
    ("source_storage_batch11_offline", [str(PYTHON), "-m", "pytest", *tests, "-q", "--no-cov", "--junitxml=" + str(RUN / "source_storage_batch11_offline.xml")]),
    ("source_storage_batch11_mypy", [str(PYTHON), "-m", "mypy", *sources]),
    ("source_storage_batch11_ruff", [str(PYTHON), "-m", "ruff", "check", *sources, "tests/unit/test_r06_default_worker_data_mode.py"]),
    ("source_storage_batch11_format", [str(PYTHON), "-m", "ruff", "format", "--check", *sources, "tests/unit/test_r06_default_worker_data_mode.py"]),
]
receipts = []
for label, command in checks:
    started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
    with (RUN / (label + ".log")).open("wb") as output:
        result = subprocess.run(command, cwd=ROOT / "backend", env=environment, stdout=output, stderr=subprocess.STDOUT, timeout=180)
    receipt = {"started_at": started, "ended_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"), "command": command, "cwd": str(ROOT / "backend"), "exit_code": result.returncode, "baseline_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(), "timeout_seconds": 180, "scope": "explicit unit/contract fixture integration; no PG/Redis/model/source HTTP; placeholder DSN has no password and never authorizes a connection"}
    (RUN / (label + ".json")).write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
    receipts.append(receipt)
    print(json.dumps({"label": label, "exit_code": result.returncode}), flush=True)
(RUN / "source_storage_batch11_checks.json").write_text(json.dumps(receipts, indent=2) + "\n", encoding="utf-8", newline="\n")
raise SystemExit(0 if all(receipt["exit_code"] == 0 for receipt in receipts) else 1)
