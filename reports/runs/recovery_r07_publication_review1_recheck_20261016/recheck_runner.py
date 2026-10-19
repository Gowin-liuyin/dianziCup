"""Record independent review commands and isolate PostgreSQL without exposing credentials."""

import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / "backend"
RAW = Path(__file__).resolve().parent
PYTHON = BACKEND / ".venv/Scripts/python.exe"
RUN_ID = "r06_catalog_r07_pub_review2_20261016"
DATABASE = "test_dianzi_" + RUN_ID
CBM = "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp"
PROJECT = "r07_pub_review2_20261016"


def record(name, argv, *, cwd=BACKEND, env=None):
    started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()
    before = time.perf_counter()
    result = subprocess.run(argv, cwd=cwd, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    elapsed = time.perf_counter() - before
    output = result.stdout + result.stderr
    if env and env.get("TEST_DATABASE_URL"):
        output = output.replace(env["TEST_DATABASE_URL"], "[redacted test connection]")
    (RAW / (name + ".log")).write_text(output, encoding="utf-8")
    metadata = {"argv": list(map(str, argv)), "cwd": str(cwd), "started_at": started,
        "completed_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
        "elapsed_seconds": elapsed, "exit_code": result.returncode,
        "code_sha": "dc04d193185324f6913cde8efc40f4b238047dd8", "log": name + ".log"}
    (RAW / (name + ".json")).write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"name": name, "exit_code": result.returncode, "elapsed_seconds": elapsed,
        "tail": output[-900:]}, ensure_ascii=False), flush=True)
    return result.returncode


def pg_environment():
    import psycopg
    from psycopg import sql
    from sqlalchemy.engine import URL
    secret = subprocess.run(["wsl", "-d", "Ubuntu-22.04", "-u", "root", "--", "cat",
        "/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json"],
        capture_output=True, text=True, check=True)
    settings = json.loads(secret.stdout)
    assert settings["postgres_port"] == 25432 or str(settings["postgres_port"]) == "25432"
    parameters = {"host": "127.0.0.1", "port": 25432, "user": settings["postgres_user"],
        "password": settings["postgres_password"], "dbname": "postgres", "connect_timeout": 5}
    with psycopg.connect(**parameters, autocommit=True) as connection:
        exists = connection.execute("SELECT datname FROM pg_database WHERE datname=%s", (DATABASE,)).fetchone()
        if exists is None:
            connection.execute(sql.SQL("CREATE DATABASE {} OWNER {}").format(sql.Identifier(DATABASE), sql.Identifier(parameters["user"])))
    parameters["dbname"] = DATABASE
    with psycopg.connect(**parameters) as connection:
        actual = connection.execute("SELECT current_database(), current_user").fetchone()
        assert actual == (DATABASE, parameters["user"])
    env = os.environ.copy()
    env["DIANZI_TEST_RUN_ID"] = RUN_ID
    env["TEST_DATABASE_URL"] = URL.create("postgresql+psycopg", username=parameters["user"], password=parameters["password"], host="127.0.0.1", port=25432, database=DATABASE).render_as_string(hide_password=False)
    env["PYTHONPATH"] = str(BACKEND / "src") + os.pathsep + str(BACKEND / "tests/integration") + os.pathsep + str(BACKEND)
    (RAW / "pg_isolation.json").write_text(json.dumps({"database": DATABASE, "run_id": RUN_ID, "actual_database_matches": True,
        "port": 25432, "fixture": "catalog_engine UUID schema + statement_timeout15000 + lock_timeout5000", "is_synthetic": True}, indent=2), encoding="utf-8")
    return env


mode = sys.argv[1]
if mode == "unit":
    record("unit_contract_234", [str(PYTHON), "-m", "pytest", "tests/contract/test_r07_signal_claim_values.py", "tests/contract/test_r02_value_contract.py", "tests/unit/test_r02_knowledge_publication_contract.py", "tests/unit/test_r07_enrichment_contracts.py", "tests/unit/test_r07_public_signals.py", "tests/contract/test_r07_public_signal_sources.py", "tests/unit/test_r07_public_signals_fix1.py", "tests/contract/test_r07_public_signals_fix1_cwe.py", "tests/unit/test_r07_cvss_authority_scope_fix.py", "tests/contract/test_r07_cvss_authority_scope_contract.py", "--no-cov", "-q", "--junitxml=" + str(RAW / "unit_contract_234.xml")])
elif mode == "pg":
    env = pg_environment()
    record("integration_pg_95", [str(PYTHON), "-m", "pytest", "tests/integration/test_r07_enrichment_inputs_pg.py", "tests/integration/test_r07_composed_claims_pg.py", "tests/integration/test_r07_enrichment_publication_pg.py", "tests/integration/test_r07_signal_claim_values_pg.py", "tests/integration/test_r07_literature_target_scope_pg.py", "tests/integration/test_r06_catalog_documents_pg.py", "tests/integration/test_r07_publication_acl_lock_fix_pg.py", "tests/integration/test_r07_cvss_authority_scope_fix_pg.py", "tests/integration/test_r07_publication_rule_provenance_pg.py", "--no-cov", "-q", "--junitxml=" + str(RAW / "integration_pg_95.xml")], env=env)
elif mode == "cbm":
    base = ["wsl", "-d", "Ubuntu-22.04", "-u", "root", "--", CBM, "cli", "--json"]
    record("cbm_schema", base + ["get_graph_schema", "--project", PROJECT], cwd=ROOT)
    record("cbm_architecture", base + ["get_architecture", "--project", PROJECT], cwd=ROOT)
    for name in ("publish_enrichment_attempts", "load_event_enrichment_inputs", "KnowledgeReadService.event_detail"):
        record("cbm_trace_" + name.replace(".", "_"), base + ["trace_path", "--project", PROJECT, "--function-name", name, "--direction", "both", "--depth", "3", "--include-evidence", "true"], cwd=ROOT)
elif mode == "checks":
    changed = subprocess.run(["git", "diff", "--name-only", "71e594cb958bd93d21fb7ed66574b3cba4cc47e1..HEAD", "--", "backend"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.splitlines()
    files = [name.removeprefix("backend/") for name in changed if name.endswith(".py")]
    record("ruff_changed", [str(PYTHON), "-m", "ruff", "check", *files])
    record("ruff_format_changed", [str(PYTHON), "-m", "ruff", "format", "--check", *files])
    record("mypy_src", [str(PYTHON), "-m", "mypy", "src"])
elif mode == "security":
    record("security", [str(PYTHON), "-m", "pytest", "tests/security", "--no-cov", "-q", "--junitxml=" + str(RAW / "security.xml")])
elif mode == "security_pg":
    record("security_pg_recheck", [str(PYTHON), "-m", "pytest", "tests/security", "--no-cov", "-q", "--junitxml=" + str(RAW / "security_pg_recheck.xml")], env=pg_environment())
elif mode == "cbm_qualified":
    base = ["wsl", "-d", "Ubuntu-22.04", "-u", "root", "--", CBM, "cli", "--json"]
    record("cbm_index_help", base + ["index_repository", "--help"], cwd=ROOT)
    record("cbm_index", base + ["index_repository", "--repo-path", "/mnt/d/wt/r07-pub-recheck1/backend/src", "--name", PROJECT, "--mode", "full", "--persistence", "false"], cwd=ROOT)
    record("cbm_schema", base + ["get_graph_schema", "--project", PROJECT], cwd=ROOT)
    record("cbm_architecture", base + ["get_architecture", "--project", PROJECT], cwd=ROOT)
    for label, name in (("publish", "ai_intel.enrichment.publication.publish_enrichment_attempts"), ("inputs", "ai_intel.enrichment.inputs.load_event_enrichment_inputs"), ("event_detail", "ai_intel.api.knowledge_read_service.KnowledgeReadService.event_detail")):
        record("cbm_qualified_" + label, base + ["trace_path", "--project", PROJECT, "--function-name", PROJECT + "." + name, "--direction", "both", "--depth", "3", "--include-evidence", "true"], cwd=ROOT)
    record("rg_callers", ["rg", "-n", "publish_enrichment_attempts|load_event_enrichment_inputs|event_detail\\(", "backend/src"], cwd=ROOT)
    for label, name in (("lock", "ai_intel.enrichment.publication._lock_input_parents"), ("source_writer", "ai_intel.ingestion.source_documents.persist_source_response"), ("registration", "ai_intel.ingestion.source_documents.ensure_source_registration")):
        record("cbm_qualified_" + label, base + ["trace_path", "--project", PROJECT, "--function-name", PROJECT + "." + name, "--direction", "both", "--depth", "3", "--include-evidence", "true"], cwd=ROOT)
    record("rg_source_worker_callers", ["rg", "-n", "persist_source_response|ensure_source_registration|persist_catalog_documents", "backend/src"], cwd=ROOT)
elif mode == "original":
    env = pg_environment()
    env["INDEPENDENT_REVIEW_RUN_SUFFIX"] = "_dc04_original"
    record("original_probe_unchanged_9", [str(PYTHON), "-m", "pytest", str(RAW / "test_original_probe_unchanged.py"), "--no-cov", "-q", "--confcutdir=" + str(ROOT), "--junitxml=" + str(RAW / "original_probe_unchanged_9.xml")], env=env)
elif mode == "independent":
    record("independent_recheck", [str(PYTHON), "-m", "pytest", str(RAW / "test_independent_recheck_pg.py"), "--no-cov", "-q", "--confcutdir=" + str(ROOT), "--junitxml=" + str(RAW / "independent_recheck.xml")], env=pg_environment())
elif mode == "independent_v2":
    record("independent_recheck_v2", [str(PYTHON), "-m", "pytest", str(RAW / "test_independent_recheck_v2_pg.py"), "--no-cov", "-q", "--confcutdir=" + str(ROOT), "--junitxml=" + str(RAW / "independent_recheck_v2.xml")], env=pg_environment())
elif mode == "negative":
    record("independent_negatives", [str(PYTHON), "-m", "pytest", str(RAW / "test_independent_publication_pg.py"), "--no-cov", "-q", "--confcutdir=" + str(ROOT), "--junitxml=" + str(RAW / "independent_negatives.xml")], env=pg_environment())
elif mode == "negative_extended":
    env = pg_environment()
    env["INDEPENDENT_REVIEW_RUN_SUFFIX"] = "_extended"
    record("independent_negatives_extended", [str(PYTHON), "-m", "pytest", str(RAW / "test_independent_publication_pg.py"), "--no-cov", "-q", "--confcutdir=" + str(ROOT), "--junitxml=" + str(RAW / "independent_negatives_extended.xml")], env=env)
elif mode == "fullpure":
    record("full_pure_regression", [str(PYTHON), "-m", "pytest", "tests/unit", "tests/contract", "tests/security", "-m", "not real_pg", "-q", "--junitxml=" + str(RAW / "full_pure_regression.xml")])
elif mode == "multisource":
    record("independent_multisource_read", [str(PYTHON), "-m", "pytest", str(RAW / "test_independent_publication_pg.py"), "-k", "multisource_model_candidate", "--no-cov", "-q", "--confcutdir=" + str(ROOT), "--junitxml=" + str(RAW / "independent_multisource_read.xml")], env=pg_environment())
else:
    raise SystemExit("unsupported review run")
