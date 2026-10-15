"""Verify the combined immutable inputs in an isolated PostgreSQL database."""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
label, mode = sys.argv[1:]
python = ROOT / "backend/.venv/Scripts/python.exe"
options = {
    "unit": ["pytest", "tests/contract/test_r07_signal_claim_values.py", "tests/contract/test_r02_value_contract.py", "tests/unit/test_r02_knowledge_publication_contract.py", "tests/unit/test_r07_enrichment_contracts.py", "tests/unit/test_r07_public_signals.py", "tests/contract/test_r07_public_signal_sources.py", "tests/unit/test_r07_public_signals_fix1.py", "tests/contract/test_r07_public_signals_fix1_cwe.py", "tests/unit/test_r07_cvss_authority_scope_fix.py", "tests/contract/test_r07_cvss_authority_scope_contract.py", "--no-cov", "-q"],
    "pg": ["pytest", "tests/integration/test_r07_enrichment_inputs_pg.py", "tests/integration/test_r07_composed_claims_pg.py", "tests/integration/test_r07_enrichment_publication_pg.py", "tests/integration/test_r07_signal_claim_values_pg.py", "tests/integration/test_r07_literature_target_scope_pg.py", "tests/integration/test_r06_catalog_documents_pg.py", "tests/integration/test_r07_publication_acl_lock_fix_pg.py", "tests/integration/test_r07_cvss_authority_scope_fix_pg.py", "tests/integration/test_r07_publication_rule_provenance_pg.py", "--no-cov", "-q"],
    "provenance": ["pytest", "tests/integration/test_r07_publication_rule_provenance_pg.py", "--no-cov", "-q"],
    "ruff": ["ruff", "check", "src", "tests"],
    "format": ["ruff", "format", "--check", "src", "tests"],
    "mypy": ["mypy", "src"],
}
environment = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONPATH=str(ROOT / "backend/src"))
for key in ("TEST_DATABASE_URL", "TEST_REDIS_URL", "DIANZI_TEST_RUN_ID"):
    environment.pop(key, None)
if mode in {"pg", "provenance"}:
    private = subprocess.run(["wsl.exe", "-d", "Ubuntu-22.04", "-u", "root", "--exec", "cat", "/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json"], capture_output=True, check=True)
    url = make_url(json.loads(private.stdout)["TEST_DATABASE_URL"])
    assert url.host in {"127.0.0.1", "localhost"} and url.database.startswith("test_dianzi_")
    run_id = "r06_catalog_r07_pub_combined_20261016"
    database = "test_dianzi_" + run_id
    engine = create_engine(url, isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as connection:
            if not connection.scalar(text("SELECT 1 FROM pg_database WHERE datname=:name"), {"name": database}):
                connection.execute(text('CREATE DATABASE "' + database + '"'))
    finally:
        engine.dispose()
    environment["TEST_DATABASE_URL"] = url.set(database=database).render_as_string(hide_password=False)
    environment["DIANZI_TEST_RUN_ID"] = run_id
argv = [str(python), "-m", *options[mode]]
if mode in {"unit", "pg", "provenance"}:
    argv.append("--junitxml=" + str(RUN / (label + ".xml")))
started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
with (RUN / (label + ".log")).open("xb") as output:
    result = subprocess.run(argv, cwd=ROOT / "backend", env=environment, stdout=output, stderr=subprocess.STDOUT, timeout=600)
receipt = {"started_at": started, "ended_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"), "cwd": str(ROOT / "backend"), "argv": argv, "exit_code": result.returncode, "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(), "working_tree": subprocess.check_output(["git", "status", "--porcelain", "--", "backend/src", "backend/tests"], cwd=ROOT, text=True).strip() or "frozen source/test tree clean", "scope": "real isolated PG; synthetic source inputs; no external model/source/provider call"}
(RUN / (label + ".json")).write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"label": label, "exit_code": result.returncode}))
raise SystemExit(result.returncode)
