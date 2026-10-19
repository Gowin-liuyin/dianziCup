"""Independent R06 review runner with private, isolated PostgreSQL resources."""

import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
SHA = "a89e94b66e240a0c958f7b7e2b8dc22e88f79348"
MATERIAL = "bdebeca358f0cfd63630b223dee64647b5280687"
PYTHON = "D:/dianzi/backend/.venv/Scripts/python.exe"
CONNECTION = "/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json"
CBM = "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp"
CACHE = "/tmp/dianzi-cbm-r06-bulk-review1-20261016"
PROJECT = "r06_bulk_review1_a89_20261016"


def now():
    return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="milliseconds")


def write(name, value):
    (RUN / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def private_url():
    from sqlalchemy.engine import make_url
    response = subprocess.run(["wsl.exe", "-d", "Ubuntu-22.04", "-u", "root", "--exec", "cat", CONNECTION], capture_output=True, check=True)
    url = make_url(json.loads(response.stdout)["TEST_DATABASE_URL"])
    assert url.host in {"127.0.0.1", "localhost"} and url.port == 25432
    assert url.database.startswith("test_") and re.fullmatch("test_[a-z0-9_]+", url.username)
    assert url.password and not url.query
    return url.set(drivername="postgresql+psycopg")


def clean_environment():
    environment = {key: value for key, value in os.environ.items() if key.upper() in {"PATH", "SYSTEMROOT", "TEMP", "TMP", "USERPROFILE", "COMSPEC", "LOCALAPPDATA", "WINDIR"}}
    environment.update(PYTHONPATH=os.pathsep.join(str(ROOT / path) for path in ("backend/src", "backend", "backend/tests/integration")), PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")
    return environment


def resource(label):
    from sqlalchemy import create_engine, text
    identity = RUN / (label + "_identity.json")
    assert not identity.exists()
    run_id = "r06_catalog_bulk_review1_" + uuid4().hex[:12]
    database = "test_dianzi_" + run_id
    url = private_url()
    admin = create_engine(url.set(database="postgres"), hide_parameters=True, isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.execute(text('CREATE DATABASE "' + database + '"'))
    admin.dispose()
    write(identity.name, {"created_at": now(), "database": database, "run_id": run_id, "postgres_port": 25432, "forward_target": "0016_source_response_receipts"})
    environment = clean_environment()
    dedicated = url.set(database=database).render_as_string(hide_password=False)
    environment.update(TEST_DATABASE_URL=dedicated, DIANZI_TEST_RUN_ID=run_id)
    return environment, (dedicated, url.password, url.render_as_string(hide_password=False))


def command(label, argv, *, cwd=ROOT, environment=None, secrets=(), timeout=240):
    assert not (RUN / (label + ".command.json")).exists()
    started, wall = now(), time.perf_counter()
    process = subprocess.Popen(argv, cwd=cwd, env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=0x08000000)
    timed_out = False
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        stdout, stderr = process.communicate(timeout=5)
        timed_out = True
    for suffix, output in (("stdout", stdout), ("stderr", stderr)):
        for secret in secrets:
            if secret:
                output = output.replace(secret.encode(), b"[redacted test connection]")
        (RUN / (label + "." + suffix + ".log")).write_bytes(output)
    record = {"started_at": started, "ended_at": now(), "wall_seconds": time.perf_counter() - wall, "argv": argv, "cwd": str(cwd), "exit_code": 124 if timed_out else process.returncode, "timeout": timed_out, "pid": process.pid, "terminated_and_waited": process.poll() is not None, "reviewed_sha": SHA}
    write(label + ".command.json", record)
    print(json.dumps(record, ensure_ascii=False), flush=True)
    return record["exit_code"]


def replay(number):
    preflight_start, preflight_wall = now(), time.perf_counter()
    assert len(list(RUN.glob("replay_*_execution_start.json"))) < 2
    previous_wall = sum(json.loads(path.read_text(encoding="utf-8"))["total_wall_seconds"] for path in RUN.glob("replay_*_controller.json"))
    assert previous_wall < 240
    label = "replay_" + number
    environment, secrets = resource(label)
    environment.update(DIAG_DATABASE_URL=environment.pop("TEST_DATABASE_URL"), DIAG_REPLAY_NUMBER=number)
    write(label + "_script_versions.json", {name: hashlib.sha256((RUN / name).read_bytes()).hexdigest() for name in ("control.py", "replay.py", "verify_raw.py")})
    code = command(label, [PYTHON, "-B", str(RUN / "replay.py")], cwd=ROOT / "backend", environment=environment, secrets=secrets, timeout=min(120, 240 - previous_wall))
    write(label + "_controller.json", {"started_at": preflight_start, "ended_at": now(), "total_wall_seconds": time.perf_counter() - preflight_wall, "exit_code": code, "all_provisioning_and_child_instrumentation_included": True})
    return code


def checks(label, arguments):
    environment, secrets = resource(label)
    temp = Path("D:/dianzi-local-evidence/r06-bulk-source-evidence-review1-20261016") / label
    temp.parent.mkdir(parents=True, exist_ok=True)
    environment["REVIEW_CHECK_LABEL"] = label
    if arguments == ["r04_adapted"]:
        argv = [PYTHON, "-B", str(RUN / "r04_runner.py")]
        environment["REVIEW_BASETEMP"] = str(temp)
    else:
        argv = [PYTHON, "-B", "-m", *arguments]
        if arguments[0] == "pytest":
            argv.extend(["--import-mode=importlib", "--no-cov", "--junitxml=" + str(RUN / (label + ".xml")), "--basetemp=" + str(temp)])
    return command(label, argv, cwd=ROOT / "backend", environment=environment, secrets=secrets)


def cbm():
    prefix = ["wsl.exe", "-d", "Ubuntu-22.04", "-u", "root", "--exec", "env", "CBM_CACHE_DIR=" + CACHE, CBM, "cli", "--json"]
    command("cbm_version", ["wsl.exe", "-d", "Ubuntu-22.04", "-u", "root", "--exec", CBM, "--version"], timeout=60)
    command("cbm_help", prefix + ["--help"], timeout=60)
    command("cbm_index", prefix + ["index_repository", "--repo-path", "/mnt/d/wt/r06-bulk-review1/backend/src", "--name", PROJECT, "--mode", "fast", "--persistence", "false"], timeout=60)
    command("cbm_schema", prefix + ["get_graph_schema", "--project", PROJECT], timeout=60)
    for function in ["build_source_page_handler", "persist_catalog_documents", "persist_source_response", "register_source_revision_blocks", "add_text_block", "attach_evidence_span", "save_document_revision", "register_response_content", "cleanup_unreferenced_object", "commit_page", "execute_job", "publish"]:
        command("cbm_trace_" + function, prefix + ["trace_path", "--function-name", function, "--project", PROJECT, "--direction", "both", "--depth", "2", "--limit", "150", "--max-output-tokens", "6000", "--include-evidence", "true"], timeout=60)


if __name__ == "__main__":
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip() == SHA
    mode, *arguments = sys.argv[1:]
    if mode == "replay":
        raise SystemExit(replay(arguments[0]))
    if mode == "checks":
        raise SystemExit(checks(arguments[0], arguments[1:]))
    if mode == "cbm":
        cbm()
    elif mode == "architecture":
        prefix = ["wsl.exe", "-d", "Ubuntu-22.04", "-u", "root", "--exec", "env", "CBM_CACHE_DIR=" + CACHE, CBM, "cli", "--json"]
        raise SystemExit(command("cbm_architecture", prefix + ["get_architecture", "--project", PROJECT, "--aspects", '["all"]', "--max-output-tokens", "6000"], timeout=60))
    elif mode == "architecture_help":
        prefix = ["wsl.exe", "-d", "Ubuntu-22.04", "-u", "root", "--exec", "env", "CBM_CACHE_DIR=" + CACHE, CBM, "cli", "--json"]
        raise SystemExit(command("cbm_architecture_help", prefix + ["get_architecture", "--help"], timeout=60))
    elif mode == "architecture_ready":
        prefix = ["wsl.exe", "-d", "Ubuntu-22.04", "-u", "root", "--exec", "env", "CBM_CACHE_DIR=" + CACHE, CBM, "cli", "--json"]
        raise SystemExit(command("cbm_architecture_ready", prefix + ["get_architecture", "--project", PROJECT, "--aspects", '["all"]'], timeout=60))
    elif mode == "architecture_all":
        prefix = ["wsl.exe", "-d", "Ubuntu-22.04", "-u", "root", "--exec", "env", "CBM_CACHE_DIR=" + CACHE, CBM, "cli", "--json"]
        raise SystemExit(command("cbm_architecture_all", prefix + ["get_architecture", "--project", PROJECT, "--aspects", "all"], timeout=60))
    elif mode == "static":
        raise SystemExit(command(arguments[0], [PYTHON, "-B", "-m", *arguments[1:]], cwd=ROOT / "backend", environment=clean_environment()))
    elif mode == "cbm_publication":
        prefix = ["wsl.exe", "-d", "Ubuntu-22.04", "-u", "root", "--exec", "env", "CBM_CACHE_DIR=" + CACHE, CBM, "cli", "--json"]
        for label, function in [("knowledge_publication", PROJECT + ".ai_intel.knowledge.persistence.KnowledgeRepository.publish"), ("dimension_publication", PROJECT + ".ai_intel.enrichment.persistence.DimensionRepository.publish")]:
            command("cbm_trace_" + label, prefix + ["trace_path", "--function-name", function, "--project", PROJECT, "--direction", "both", "--depth", "2", "--limit", "150", "--max-output-tokens", "6000", "--include-evidence", "true"], timeout=60)
    elif mode == "audit":
        raise SystemExit(command("audit", [PYTHON, "-B", str(RUN / "audit.py")], environment=clean_environment()))
    elif mode == "audit_ready":
        raise SystemExit(command("audit_ready", [PYTHON, "-B", str(RUN / "audit.py")], environment=clean_environment()))
    elif mode == "audit_final":
        raise SystemExit(command("audit_final", [PYTHON, "-B", str(RUN / "audit.py"), "audit_final_receipt.json"], environment=clean_environment()))
    else:
        raise SystemExit(2)
