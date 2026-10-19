"""Record bounded local checks with private PG credentials kept out of artifacts."""

import hashlib
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
RUN_ID = "r06_catalog_r07_pub_fix_20261016"
DATABASE = "test_dianzi_" + RUN_ID
CBM = "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp"
PROJECT = "r07_pub_acl_lock_fix_20261016"


def record(name, argv, *, cwd=BACKEND, env=None):
    started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()
    before = time.perf_counter()
    result = subprocess.run(argv, cwd=cwd, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    output = result.stdout + result.stderr
    if env and env.get("TEST_DATABASE_URL"):
        output = output.replace(env["TEST_DATABASE_URL"], "[redacted test connection]")
    (RAW / (name + ".log")).write_text(output, encoding="utf-8")
    metadata = {"argv": list(map(str, argv)), "cwd": str(cwd), "started_at": started,
        "completed_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
        "elapsed_seconds": time.perf_counter() - before, "exit_code": result.returncode,
        "code_sha": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip(),
        "source_hashes": {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in (BACKEND / "src/ai_intel/enrichment/inputs.py", BACKEND / "src/ai_intel/enrichment/publication.py")},
        "log": name + ".log"}
    (RAW / (name + ".json")).write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"name": name, "exit_code": result.returncode, "elapsed_seconds": metadata["elapsed_seconds"], "tail": output[-900:]}, ensure_ascii=False), flush=True)
    return result.returncode


def pg_environment():
    import psycopg
    from psycopg import sql
    from sqlalchemy.engine import URL
    secret = subprocess.run(["wsl", "-d", "Ubuntu-22.04", "-u", "root", "--", "cat", "/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json"], capture_output=True, text=True, check=True)
    settings = json.loads(secret.stdout)
    assert int(settings["postgres_port"]) == 25432
    parameters = {"host": "127.0.0.1", "port": 25432, "user": settings["postgres_user"], "password": settings["postgres_password"], "dbname": "postgres", "connect_timeout": 5}
    with psycopg.connect(**parameters, autocommit=True) as connection:
        if connection.execute("SELECT datname FROM pg_database WHERE datname=%s", (DATABASE,)).fetchone() is None:
            connection.execute(sql.SQL("CREATE DATABASE {} OWNER {}").format(sql.Identifier(DATABASE), sql.Identifier(parameters["user"])))
    parameters["dbname"] = DATABASE
    with psycopg.connect(**parameters) as connection:
        assert connection.execute("SELECT current_database(), current_user").fetchone() == (DATABASE, parameters["user"])
    env = os.environ.copy()
    env["DIANZI_TEST_RUN_ID"] = RUN_ID
    env["TEST_DATABASE_URL"] = URL.create("postgresql+psycopg", username=parameters["user"], password=parameters["password"], host="127.0.0.1", port=25432, database=DATABASE).render_as_string(hide_password=False)
    env["PYTHONPATH"] = str(BACKEND / "src") + os.pathsep + str(BACKEND / "tests/integration") + os.pathsep + str(BACKEND)
    (RAW / "pg_isolation.json").write_text(json.dumps({"database": DATABASE, "run_id": RUN_ID, "actual_database_matches": True, "port": 25432, "fixture": "catalog_engine UUID schema; statement_timeout15000; lock_timeout5000", "is_synthetic": True}, indent=2), encoding="utf-8")
    return env


mode, label = sys.argv[1:3]
if mode == "negative":
    env = pg_environment()
    env["INDEPENDENT_REVIEW_RUN_SUFFIX"] = "_" + label
    record(label, [str(PYTHON), "-m", "pytest", str(RAW / "byteblob/test_independent_publication_pg.py"), "--no-cov", "-q", "--confcutdir=" + str(ROOT), "--junitxml=" + str(RAW / (label + ".xml"))], env=env)
elif mode == "checks":
    for kind, arguments in (("ruff", ["ruff", "check", "src/ai_intel/enrichment/inputs.py", "src/ai_intel/enrichment/publication.py", "tests/integration/test_r07_publication_acl_lock_fix_pg.py"]), ("format", ["ruff", "format", "--check", "src/ai_intel/enrichment/inputs.py", "src/ai_intel/enrichment/publication.py", "tests/integration/test_r07_publication_acl_lock_fix_pg.py"]), ("mypy", ["mypy", "src"])):
        record(label + "_" + kind, [str(PYTHON), "-m", *arguments])
elif mode == "cbm":
    base = ["wsl", "-d", "Ubuntu-22.04", "-u", "root", "--", CBM, "cli", "--json"]
    record(label + "_index", base + ["index_repository", "--repo-path", "/mnt/d/wt/r07-pub-fix/backend/src", "--name", PROJECT, "--mode", "full", "--persistence", "false"], cwd=ROOT)
    record(label + "_schema", base + ["get_graph_schema", "--project", PROJECT], cwd=ROOT)
    for name in ("ai_intel.enrichment.publication.publish_enrichment_attempts", "ai_intel.enrichment.inputs.load_event_enrichment_inputs", "ai_intel.ingestion.source_documents.persist_source_response", "ai_intel.ingestion.catalog_documents.persist_catalog_documents", "ai_intel.knowledge.event_linking.EventRepository.publish_events"):
        record(label + "_" + name.rsplit(".", 1)[-1], base + ["trace_path", "--project", PROJECT, "--function-name", PROJECT + "." + name, "--direction", "both", "--depth", "3", "--include-evidence", "true"], cwd=ROOT)
    record(label + "_rg", ["rg", "-n", "publish_enrichment_attempts|load_event_enrichment_inputs|persist_source_response|persist_catalog_documents|save_document_revision|publish_events|publish_document", "backend/src"], cwd=ROOT)
elif mode == "pytest":
    record(label, [str(PYTHON), "-m", "pytest", *sys.argv[3:], "--no-cov", "-q", "--junitxml=" + str(RAW / (label + ".xml"))], env=pg_environment())
elif mode == "scan":
    from sqlalchemy.engine import make_url
    env = pg_environment()
    env["DIANZI_SCAN_PG_PASSWORD"] = make_url(env["TEST_DATABASE_URL"]).password
    record(label, [str(PYTHON), str(ROOT / "scripts/security_scan.py"), "--repository-root", str(ROOT), "--secret-env", "DIANZI_SCAN_PG_PASSWORD", "--secret-env", "TEST_DATABASE_URL"], cwd=ROOT, env=env)
else:
    raise SystemExit("unsupported check")
