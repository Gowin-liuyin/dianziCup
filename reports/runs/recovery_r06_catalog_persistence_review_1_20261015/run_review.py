"""Own fixed-commit review ledger; credentials stay in child process environment."""

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(os.environ.get("REVIEW_FIXED_ROOT", Path(__file__).resolve().parents[3]))
RUN = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
PYTHON = BACKEND / ".venv/Scripts/python.exe"
SHA = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
CBM = "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp"
CACHE = "/tmp/dianzi-cbm-r06-catalog-review-1-20261015"
PROJECT = "r06-catalog-review-1"

if sys.argv[1] in {"checks", "old_pg", "probes", "final_checks", "final_old_pg"}:
    raise SystemExit("Retired mixed test modes: see report scope errors; run only explicit schema-isolated targets.")


def now():
    return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")


def run(label, argv, cwd=ROOT, env=None):
    label = os.environ.get("REVIEW_RUN_PREFIX", "") + label
    started = now()
    child_env = dict(os.environ if env is None else env)
    child_env["PYTHONIOENCODING"] = "utf-8"
    output = subprocess.run(argv, cwd=cwd, capture_output=True, check=False, env=child_env)
    stdout, stderr = output.stdout, output.stderr
    for key in ("TEST_DATABASE_URL", "TEST_REDIS_URL"):
        value = child_env.get(key)
        if value:
            stdout = stdout.replace(value.encode(), b"[redacted connection]")
            stderr = stderr.replace(value.encode(), b"[redacted connection]")
    (RUN / (label + ".stdout.log")).write_bytes(stdout)
    (RUN / (label + ".stderr.log")).write_bytes(stderr)
    record = {
        "label": label, "started_at": started, "ended_at": now(),
        "argv": argv, "cwd": str(cwd), "exit_code": output.returncode,
        "sha": SHA, "stdout": label + ".stdout.log", "stderr": label + ".stderr.log",
        "stdout_sha256": hashlib.sha256(stdout).hexdigest(),
        "stderr_sha256": hashlib.sha256(stderr).hexdigest(),
    }
    with (RUN / "commands.jsonl").open("a", encoding="utf-8") as ledger:
        ledger.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(json.dumps({"label": label, "exit_code": output.returncode}), flush=True)
    return output.returncode


def cbm(label, *args):
    return run(label, ["wsl.exe", "-d", "Ubuntu-22.04", "-u", "root", "--exec",
                       "env", "CBM_CACHE_DIR=" + CACHE, CBM, "cli", "--json", *args])


def load_connection(path):
    result = subprocess.run(["wsl.exe", "-d", "Ubuntu-22.04", "-u", "root", "--exec",
                             "cat", path], capture_output=True, check=True)
    return json.loads(result.stdout)


def database_env():
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url
    from uuid import uuid4

    configuration = load_connection(
        "/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json"
    )
    url = make_url(configuration["TEST_DATABASE_URL"])
    suffix_path = RUN / "database_identity.json"
    if suffix_path.exists():
        database = json.loads(suffix_path.read_text())["database"]
    else:
        database = "test_dianzi_r06_catalog_review_" + uuid4().hex[:8]
        engine = create_engine(url, isolation_level="AUTOCOMMIT")
        with engine.connect() as connection:
            connection.execute(text('CREATE DATABASE "' + database + '"'))
        engine.dispose()
        suffix_path.write_text(json.dumps({"database": database, "created_at": now(),
                                           "purpose": "review only; new isolated database"}) + "\n")
    env = dict(os.environ)
    env["TEST_DATABASE_URL"] = url.set(database=database).render_as_string(hide_password=False)
    env["DIANZI_TEST_RUN_ID"] = database.removeprefix("test_dianzi_")
    return env


if sys.argv[1] == "setup":
    run("frozen_sync", ["uv", "sync", "--offline", "--frozen", "--extra", "semantic"], BACKEND)
    run("git_identity", ["git", "show", "--no-patch", "--format=%H%n%T%n%ci", "HEAD"])
    run("git_initial_status", ["git", "status", "--short"])
    run("diff_scope", ["git", "diff", "--name-status", "1927eeb00a7e0c1335f76340b0382f46102f08f2", SHA])
    run("diff_check", ["git", "diff", "--check", "1927eeb00a7e0c1335f76340b0382f46102f08f2", SHA])
elif sys.argv[1] == "graph":
    cbm("cbm_index_help", "index_repository", "--help")
    cbm("cbm_trace_help", "trace_path", "--help")
    cbm("cbm_index", "index_repository", "--repo-path", "/mnt/d/wt/r06-catalog-review-final/backend/src",
        "--name", PROJECT, "--mode", "fast")
    cbm("cbm_schema", "get_graph_schema", "--project", PROJECT)
    for function in ("save_document_revision", "ensure_source_registration", "persist_catalog_documents",
                     "persist_source_response", "build_source_page_handler", "register_response_content",
                     "cleanup_unreferenced_object"):
        cbm("cbm_trace_" + function, "trace_path", "--function-name", function, "--project", PROJECT,
            "--direction", "both", "--depth", "2", "--limit", "100", "--max-output-tokens", "5000",
            "--include-evidence", "true")
elif sys.argv[1] == "checks":
    run("ruff_check", [str(PYTHON), "-m", "ruff", "check", "src", "tests"], BACKEND)
    run("ruff_format", [str(PYTHON), "-m", "ruff", "format", "--check", "src", "tests"], BACKEND)
    run("mypy", [str(PYTHON), "-m", "mypy", "src"], BACKEND)
    env = database_env()
    env["COVERAGE_FILE"] = str(RUN / "combined.coverage")
    run("catalog_pure_combined", [str(PYTHON), "-m", "pytest", "tests/unit", "tests/contract",
        "tests/security", "tests/integration/test_r06_catalog_documents_pg.py", "-q",
        "--junitxml=" + str(RUN / "catalog_pure_combined.xml")], BACKEND, env)
elif sys.argv[1] == "old_pg":
    from sqlalchemy.engine import make_url
    private = load_connection(
        "/tmp/dianzi-docker-static-r01-20261014/runtime/r05-pgvector/connection.json"
    )
    env = dict(os.environ)
    env["TEST_DATABASE_URL"] = private["TEST_DATABASE_URL"]
    env["DIANZI_TEST_RUN_ID"] = "r05_pgvector_20261015"
    env["COVERAGE_FILE"] = str(RUN / "old_pg.coverage")
    files = ["tests/integration/test_r05_vector_persistence.py",
             "tests/integration/test_r05_question_api_pg.py"]
    run("old_vector_question_combined", [str(PYTHON), "-m", "pytest", "tests/unit", "tests/contract",
        "tests/security", *files, "-q", "--junitxml=" + str(RUN / "old_vector_question_combined.xml")], BACKEND, env)
elif sys.argv[1] == "probes":
    env = database_env()
    env["COVERAGE_FILE"] = str(RUN / "probes.coverage")
    run("independent_pg_probes", [str(PYTHON), "-m", "pytest", "tests/unit", "tests/contract",
        "tests/security", str(RUN / "test_review_pg_probes.py"), "-q",
        "--junitxml=" + str(RUN / "independent_pg_probes.xml")], BACKEND, env)
elif sys.argv[1] == "graph_schema":
    cbm("cbm_schema_corrected", "get_graph_schema", "--project", PROJECT)
elif sys.argv[1] == "quick_probes":
    run("independent_pg_assertion_probes_schema_only_confirmed", [str(PYTHON), str(RUN / "probe_driver.py")], ROOT, database_env())
elif sys.argv[1] == "source_audit":
    run("source_caller_rg", ["rg", "-n", "save_document_revision\\(|ensure_source_registration\\(|persist_catalog_documents\\(|register_response_content\\(|cleanup_unreferenced_object\\(", "backend/src"])
    run("source_diff", ["git", "diff", "1927eeb00a7e0c1335f76340b0382f46102f08f2", SHA, "--", "backend/src", "backend/migrations", "backend/tests"])
    run("final_tracked_status", ["git", "status", "--short", "--untracked-files=no"])
elif sys.argv[1] == "scan":
    from sqlalchemy.engine import make_url

    env = database_env()
    env["REVIEW_RESOURCE_PASSWORD"] = make_url(env["TEST_DATABASE_URL"]).password
    run("security_scan", [str(PYTHON), str(ROOT / "scripts/security_scan.py"),
        "--repository-root", str(ROOT), "--secret-env", "TEST_DATABASE_URL",
        "--secret-env", "REVIEW_RESOURCE_PASSWORD"], ROOT, env)
elif sys.argv[1] == "final_checks":
    run("ruff_check", [str(PYTHON), "-m", "ruff", "check", "src", "tests"], BACKEND)
    run("ruff_format", [str(PYTHON), "-m", "ruff", "format", "--check", "src", "tests"], BACKEND)
    run("mypy", [str(PYTHON), "-m", "mypy", "src"], BACKEND)
    env = database_env()
    env["COVERAGE_FILE"] = str(RUN / "final_catalog.coverage")
    excludes = ["--ignore=tests/security/test_r02_auth_state_boundaries.py",
                "--ignore=tests/security/test_r03_executor_authorization.py",
                "--ignore=tests/contract/test_t07_jobs_outbox.py"]
    run("catalog_probes_and_pure", [str(PYTHON), "-m", "pytest", "tests/unit", "tests/contract",
        "tests/security", *excludes, "tests/integration/test_r06_catalog_documents_pg.py",
        str(RUN / "test_review_pg_probes.py"), "-q",
        "--junitxml=" + str(RUN / "final_catalog_probes_and_pure.xml")], BACKEND, env)
elif sys.argv[1] == "final_old_pg":
    private = load_connection(
        "/tmp/dianzi-docker-static-r01-20261014/runtime/r05-pgvector/connection.json"
    )
    env = dict(os.environ)
    env["TEST_DATABASE_URL"] = private["TEST_DATABASE_URL"]
    env["DIANZI_TEST_RUN_ID"] = "r05_pgvector_20261015"
    env["COVERAGE_FILE"] = str(RUN / "final_old_pg.coverage")
    excludes = ["--ignore=tests/security/test_r02_auth_state_boundaries.py",
                "--ignore=tests/security/test_r03_executor_authorization.py",
                "--ignore=tests/contract/test_t07_jobs_outbox.py"]
    run("old_vector_question_pure", [str(PYTHON), "-m", "pytest", "tests/unit", "tests/contract",
        "tests/security", *excludes, "tests/integration/test_r05_vector_persistence.py",
        "tests/integration/test_r05_question_api_pg.py", "-q",
        "--junitxml=" + str(RUN / "final_old_vector_question_pure.xml")], BACKEND, env)
elif sys.argv[1] == "numeric_probe":
    run("numeric_metadata_replay", [str(PYTHON), str(RUN / "numeric_metadata_probe.py")], ROOT, database_env())
elif sys.argv[1] == "catalog_only":
    env = database_env()
    env["COVERAGE_FILE"] = str(RUN / "jsonb45_catalog_only.coverage")
    run("catalog_only", [str(PYTHON), "-m", "pytest",
        "tests/integration/test_r06_catalog_documents_pg.py", "-q",
        "--junitxml=" + str(RUN / "jsonb45_catalog_only.xml")], BACKEND, env)
elif sys.argv[1] == "public_snapshot":
    run("shared_public_read_only_snapshot", [str(PYTHON), str(RUN / "snapshot_shared_public.py"),
        "snapshot_module_import"], ROOT)
elif sys.argv[1] == "graph45":
    CACHE = "/tmp/dianzi-cbm-r06-catalog-review-45ee-20261015"
    PROJECT = "r06-catalog-review-45ee"
    cbm("cbm_index", "index_repository", "--repo-path", "/mnt/d/wt/r06-catalog-review-jsonb/backend/src",
        "--name", PROJECT, "--mode", "fast")
    cbm("cbm_schema", "get_graph_schema", "--project", PROJECT)
    for function in ("save_document_revision", "ensure_source_registration", "persist_catalog_documents"):
        cbm("cbm_trace_" + function, "trace_path", "--function-name", function, "--project", PROJECT,
            "--direction", "both", "--depth", "2", "--limit", "100", "--max-output-tokens", "5000",
            "--include-evidence", "true")
