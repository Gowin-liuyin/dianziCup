"""Record bounded document checks without including private connection arguments."""

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
RUN = Path(__file__).resolve().parent
PYTHON = ROOT / "backend/.venv/Scripts/python.exe"
RUN_ID = "r06_catalog_r07_publication_20261016"


def now() -> str:
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def main() -> int:
    label, mode = sys.argv[1:]
    environment = dict(
        os.environ, PYTHONPATH=str(ROOT / "backend/src"), PYTHONIOENCODING="utf-8"
    )
    environment.pop("TEST_DATABASE_URL", None)
    environment.pop("TEST_REDIS_URL", None)
    environment.pop("DIANZI_TEST_RUN_ID", None)
    if mode in {"pg", "roster", "subset"}:
        private = subprocess.run(
            [
                "wsl.exe",
                "-d",
                "Ubuntu-22.04",
                "-u",
                "root",
                "--exec",
                "cat",
                "/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json",
            ],
            capture_output=True,
            check=True,
        )
        url = make_url(json.loads(private.stdout)["TEST_DATABASE_URL"])
        assert url.host in {"127.0.0.1", "localhost"} and url.database.startswith(
            "test_dianzi_"
        )
        database = "test_dianzi_" + RUN_ID
        base = create_engine(url, isolation_level="AUTOCOMMIT")
        try:
            with base.connect() as connection:
                if not connection.scalar(
                    text("SELECT 1 FROM pg_database WHERE datname=:name"),
                    {"name": database},
                ):
                    connection.execute(text('CREATE DATABASE "' + database + '"'))
        finally:
            base.dispose()
        environment["TEST_DATABASE_URL"] = url.set(database=database).render_as_string(
            hide_password=False
        )
        environment["DIANZI_TEST_RUN_ID"] = RUN_ID
    options = {
        "roster": ["pytest", "tests/integration/test_r07_enrichment_publication_pg.py", "-k", "snapshot_revision_roster", "--no-cov", "-q"],
        "subset": ["pytest", "tests/integration/test_r07_enrichment_publication_pg.py", "-k", "drop_one_of_two", "--no-cov", "-q"],
        "unit": ["pytest", "tests/contract/test_r07_signal_claim_values.py", "tests/contract/test_r02_value_contract.py", "tests/unit/test_r02_knowledge_publication_contract.py", "tests/unit/test_r07_enrichment_contracts.py", "tests/unit/test_r07_public_signals.py", "tests/contract/test_r07_public_signal_sources.py", "tests/unit/test_r07_public_signals_fix1.py", "tests/contract/test_r07_public_signals_fix1_cwe.py", "--no-cov", "-q"],
        "cursor": [
            "pytest",
            "tests/unit/test_r06_document_cursor.py",
            "--no-cov",
            "-q",
        ],
        "pg": [
            "pytest", "tests/integration/test_r07_enrichment_inputs_pg.py", "tests/integration/test_r07_composed_claims_pg.py", "tests/integration/test_r07_enrichment_publication_pg.py", "tests/integration/test_r07_signal_claim_values_pg.py", "tests/integration/test_r07_literature_target_scope_pg.py", "tests/integration/test_r06_catalog_documents_pg.py",

            "--no-cov", "-q",
        ],
        "pure": [
            "pytest",
            "tests/unit",
            "tests/contract",
            "tests/security",
            "-m",
            "not real_pg",
            "-q",
        ],
        "ruff": ["ruff", "check", "src", "tests"],
        "mypy": ["mypy", "src"],
        "format": ["ruff", "format", "--check", "src", "tests"],
        "format_apply": ["ruff", "format", "src/ai_intel/knowledge/persistence.py", "src/ai_intel/api/knowledge_read_service.py", "src/ai_intel/enrichment/inputs.py", "src/ai_intel/enrichment/publication.py", "tests/integration/test_r07_enrichment_inputs_pg.py", "tests/integration/test_r07_composed_claims_pg.py", "tests/integration/test_r07_enrichment_publication_pg.py"],
        "ruff_apply": ["ruff", "check", "--fix", "src/ai_intel/knowledge/persistence.py", "src/ai_intel/api/knowledge_read_service.py", "src/ai_intel/enrichment/inputs.py", "src/ai_intel/enrichment/publication.py", "tests/integration/test_r07_enrichment_inputs_pg.py", "tests/integration/test_r07_composed_claims_pg.py", "tests/integration/test_r07_enrichment_publication_pg.py"],
    }
    argv = [str(PYTHON), "-m", *options[mode]]
    if mode in {"cursor", "pg", "roster", "subset", "pure", "unit"}:
        argv.append("--junitxml=" + str(RUN / (label + ".xml")))
    started = now()
    with (RUN / (label + ".log")).open("wb") as output:
        result = subprocess.run(
            argv,
            cwd=ROOT / "backend",
            env=environment,
            stdout=output,
            stderr=subprocess.STDOUT,
            timeout=600,
            check=False,
        )
    (RUN / (label + ".json")).write_text(
        json.dumps(
            {
                "argv": argv,
                "cwd": str(ROOT / "backend"),
                "started_at": started,
                "ended_at": now(),
                "exit_code": result.returncode,
                "head": subprocess.check_output(
                    ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
                ).strip(),
                "working_tree": subprocess.check_output(["git", "status", "--porcelain", "--", "backend/src", "backend/tests", "frontend/src", "frontend/e2e", "infra"], cwd=ROOT, text=True).strip() or "tracked product/test tree clean",
                "scope": "synthetic fixture input; real own UUID PG schema; not source/model live",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"label": label, "exit_code": result.returncode}))
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
