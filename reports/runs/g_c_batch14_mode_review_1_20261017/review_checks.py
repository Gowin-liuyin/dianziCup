"""Independent bounded checks of the frozen mode and migration lifecycle slice."""

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
SHARED = ROOT / "reports/runs/recovery_reviewed_integration_20261016"
sys.path.insert(0, str(SHARED))
import batch13_checks_helper as checks

checks.ROOT = ROOT
checks.RUN = RUN
checks.BASELINE = "bc089809c03472582f6256b495a6f9a2a308a5d2"
checks.QUALIFIED = "48f96b5ba35d19f5e26868a2bccd5b124afb2bd0"

CORE = [
    "tests/unit/test_r06_revision_mode.py",
    "tests/unit/test_r06_revision_mode_reads.py",
    "tests/unit/test_r07_source_report_revision_mode.py",
    "tests/unit/test_r07_source_report_reader.py",
    "tests/unit/test_r07_structured_fact_proofs.py",
    "tests/unit/test_r18_public_read_boundaries.py",
    "tests/contract/test_r06_revision_mode_router_contract.py",
    "tests/unit/test_r01_migration_engine_disposal.py",
    "tests/unit/test_r01_migration_pg_helpers.py",
    "tests/contract/test_r01_migration_configuration.py",
]
RELATED = [
    "tests/unit/test_r06_document_contracts.py",
    "tests/unit/test_r06_document_cursor.py",
    "tests/unit/test_r04_knowledge_api_cursor.py",
    "tests/unit/test_r06_source_data_mode.py",
    "tests/contract/test_r06_source_data_mode_contract.py",
    "tests/unit/test_r07_source_report_node.py",
    "tests/unit/test_r14_shared_read_consumers.py",
]
COLLECT = [
    "tests/integration/test_r06_revision_mode_read_pg.py",
    "tests/integration/test_r06_source_data_mode_pg.py",
    "tests/integration/test_r06_document_api_pg.py",
    "tests/integration/test_r04_knowledge_api_pg.py",
    "tests/integration/test_r07_structured_fact_proofs_pg.py",
    "tests/integration/test_r01_migration_engine_disposal_pg.py",
]
MODE_SOURCES = [
    "src/ai_intel/knowledge/revision_mode.py",
    "src/ai_intel/api/document_read_service.py",
    "src/ai_intel/api/document_routes.py",
    "src/ai_intel/api/knowledge_read_service.py",
    "src/ai_intel/api/knowledge_routes.py",
    "src/ai_intel/api/public_extension_reads.py",
    "src/ai_intel/knowledge/structured_fact_proofs.py",
    "src/ai_intel/infrastructure/database.py",
    "migrations/env.py",
]


def main():
    action = sys.argv[1]
    if action in {"core", "related"}:
        selected = CORE if action == "core" else RELATED
        command = [checks.PYTHON, "-m", "pytest", *selected, "--no-cov", "-q",
                   "--junitxml=" + str(RUN / (action + ".xml"))]
    elif action == "collect":
        command = [checks.PYTHON, "-m", "pytest", *COLLECT, "--collect-only", "--no-cov", "-q"]
    elif action == "default_collect":
        command = [checks.PYTHON, "-m", "pytest", str(RUN / "test_default_mode_pg.py"), "--collect-only", "--no-cov", "-q"]
    elif action == "recheck_contract":
        command = [checks.PYTHON, "-m", "pytest", str(RUN / "test_fixed_revision_mode_fixture_input_contract.py"), "--no-cov", "-q", "--junitxml=" + str(RUN / "recheck_contract.xml")]
    elif action == "ruff":
        command = [checks.PYTHON, "-m", "ruff", "check", *MODE_SOURCES, *CORE, COLLECT[0], COLLECT[4], COLLECT[5]]
    elif action == "format":
        command = [checks.PYTHON, "-m", "ruff", "format", "--check", *MODE_SOURCES, *CORE, COLLECT[0], COLLECT[4], COLLECT[5]]
    elif action == "mypy":
        command = [checks.PYTHON, "-m", "mypy", "src"]
    else:
        raise ValueError("unknown independent check")
    result = checks.execute(action, command)
    hashes = {str(path.relative_to(ROOT)).replace("\\", "/"): hashlib.sha256(path.read_bytes()).hexdigest()
              for path in RUN.iterdir() if path.is_file() and path.suffix in {".log", ".xml"}}
    (RUN / (action + ".rawhash.json")).write_text(json.dumps(hashes, indent=2) + "\n", encoding="utf-8")
    raise SystemExit(result)


if __name__ == "__main__":
    main()
