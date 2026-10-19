"""Bounded independent checks. Actual connection credentials stay in memory and environment."""

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
PYTHON = Path("D:/dianzi/backend/.venv/Scripts/python.exe")
CLI = "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp"
DATABASE = "test_dianzi_r11_assessment_review1_20261016_" + uuid4().hex[:12]
SECRETS = set()
sys.path.insert(0, str(ROOT / "backend/src"))
spec = importlib.util.spec_from_file_location("fixed_backend_redaction_before_connections", ROOT / "backend/tests/conftest.py")
HOOK = importlib.util.module_from_spec(spec)
spec.loader.exec_module(HOOK)


def now():
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def redact(value):
    for secret in sorted(SECRETS, key=len, reverse=True):
        if secret:
            value = value.replace(secret, "[redacted registered actual secret]")
    return HOOK.redact_test_connection_output(value, tuple(SECRETS))


def connection():
    captured = subprocess.run(["wsl", "-u", "root", "-e", "cat", "/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json"], capture_output=True, timeout=15, check=True)
    configuration = json.loads(captured.stdout)
    for key, value in configuration.items():
        if isinstance(value, str) and ("URL" in key or "PASSWORD" in key):
            SECRETS.add(value)
            if "URL" in key:
                password = make_url(value).password
                if password:
                    SECRETS.add(password)
    return make_url(configuration["TEST_DATABASE_URL"])


def record(label, command, cwd, started, elapsed, code):
    item = dict(label=label, command=command, cwd=str(cwd), started_at=started, finished_at=now(), elapsed_seconds=round(elapsed, 3), exit_code=code)
    with (RUN / "commands.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(item, ensure_ascii=False) + "\n")
    print(json.dumps(item, ensure_ascii=False))


def run(label, command, cwd=ROOT, environment=None, timeout=60):
    started, tick = now(), time.monotonic()
    result = subprocess.run(command, cwd=cwd, env=environment, capture_output=True, timeout=timeout, check=False)
    for name, value in (("stdout", result.stdout), ("stderr", result.stderr)):
        (RUN / f"{label}.{name}.log").write_text(redact(value.decode("utf-8", errors="replace")), encoding="utf-8")
    record(label, command, cwd, started, time.monotonic() - tick, result.returncode)
    return result.returncode


def cbm():
    project = "r11-pg-assessments-review1-20261016-" + uuid4().hex[:8]
    tasks = [
        ("cbm_src_index", ["index_repository", "--repo-path", "/mnt/d/wt/r11-pg-assessments-review1/backend/src", "--name", project, "--mode", "fast"]),
        ("cbm_assets_index", ["index_repository", "--repo-path", "/mnt/d/wt/r11-pg-assessments-review1/backend/src/ai_intel/assets", "--name", project + "-assets", "--mode", "fast"]),
        ("cbm_schema", ["get_graph_schema", "--project", project]),
        ("cbm_architecture", ["get_architecture", "--project", project, "--aspects", "all"]),
    ]
    for method in ("prepare", "commit", "read"):
        tasks.append(("cbm_assessment_" + method, ["trace_path", "--project", project, "--function-name", project + ".ai_intel.assessment.assessment_service.AssessmentService." + method, "--direction", "outbound", "--depth", "2", "--limit", "60"]))
    for method in ("create_candidate", "record_leaf_review", "validate", "publish", "retire"):
        tasks.append(("cbm_rule_" + method, ["trace_path", "--project", project, "--function-name", project + ".ai_intel.assessment.rule_service.RuleService." + method, "--direction", "outbound", "--depth", "2", "--limit", "60"]))
    tasks.append(("cbm_assets_writer", ["trace_path", "--project", project + "-assets", "--function-name", project + "-assets.inventory.InventoryService.import_manifest", "--direction", "outbound", "--depth", "2", "--limit", "60"]))
    for label, arguments in tasks:
        if run(label, ["wsl", "-e", CLI, "cli", "--json", *arguments]):
            raise RuntimeError("CBM task failed: " + label)
    run("callers_rg", ["rg", "-n", "RuleService|AssessmentService|lock_rule_inputs|load_rule_inputs|save_document_revision|persist_source_response|KnowledgeRepository|import_manifest", "backend/src", "backend/tests"])


def prepare(base):
    assert base.host in {"127.0.0.1", "localhost"} and base.port == 25432
    tick, started = time.monotonic(), now()
    admin = create_engine(base.set(database="postgres"), isolation_level="AUTOCOMMIT", hide_parameters=True)
    with admin.connect() as connection:
        assert not connection.scalar(text("SELECT 1 FROM pg_database WHERE datname=:name"), dict(name=DATABASE))
        connection.exec_driver_sql(f'CREATE DATABASE "{DATABASE}"')
    admin.dispose()
    schema = "r11_review1_" + uuid4().hex
    engine = create_engine(base.set(database=DATABASE), hide_parameters=True)
    with engine.begin() as connection:
        connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
    engine.dispose()
    scoped = base.set(database=DATABASE).update_query_dict(dict(options=f"-csearch_path={schema} -cstatement_timeout=15000 -clock_timeout=5000"))
    SECRETS.add(scoped.render_as_string(hide_password=False))
    from ai_intel.infrastructure.database import run_migrations
    from ai_intel.assessment.rule_persistence import RULE_TABLES
    from ai_intel.assessment.assessment_persistence import ASSESSMENT_TABLES
    run_migrations(scoped.render_as_string(hide_password=False), "0019_aggregate_observations")
    engine = create_engine(scoped, hide_parameters=True)
    with engine.begin() as connection:
        for table in (*RULE_TABLES, *ASSESSMENT_TABLES):
            table.create(connection)
    reflection = {}
    with engine.connect() as connection:
        inspector = inspect(connection)
        for table in (*RULE_TABLES, *ASSESSMENT_TABLES):
            reflection[table.name] = dict(columns=inspector.get_columns(table.name), pk=inspector.get_pk_constraint(table.name), unique=inspector.get_unique_constraints(table.name), checks=inspector.get_check_constraints(table.name), fks=inspector.get_foreign_keys(table.name), indexes=inspector.get_indexes(table.name))
        reflection["actual_triggers"] = [dict(row) for row in connection.execute(text("SELECT c.relname, t.tgname, pg_get_triggerdef(t.oid) AS definition FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=:schema AND NOT t.tgisinternal ORDER BY c.relname,t.tgname"), dict(schema=schema)).mappings()]
        revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
    engine.dispose()
    (RUN / "six_table_reflection.json").write_text(json.dumps(reflection, default=str, indent=2), encoding="utf-8")
    (RUN / "database_receipt.json").write_text(json.dumps(dict(database=DATABASE, schema=schema, migration=revision, forward_only=True, production_0021="not_run", fixture_data=True, started_at=started, finished_at=now()), indent=2), encoding="utf-8")
    record("prepare_dedicated_pg", ["review_runner.py", "prepare", "forward 0019 + six local tables"], ROOT, started, time.monotonic()-tick, 0)
    return scoped


def seal():
    findings = []
    report = ROOT / "reports/reviews/recovery/G-D-R11-pg-assessments-review-1.md"
    for path in [*sorted(RUN.rglob("*")), report]:
        if path.is_file() and "__pycache__" not in path.parts and path.name not in {"secret_scan.json", "artifact_manifest.json", "delivery_receipt.json"}:
            content = path.read_bytes()
            for secret in SECRETS:
                if secret and secret.encode() in content:
                    findings.append(dict(path=str(path.relative_to(ROOT)), match_kind="registered_actual_secret"))
    scan = dict(actual_values_registered=len(SECRETS), matches=findings, match_count=len(findings), regex_only=False, hook_loaded_before_connection=True, checked_at=now())
    (RUN / "secret_scan.json").write_text(json.dumps(scan, indent=2), encoding="utf-8")
    entries = [dict(path=str(p.relative_to(ROOT)).replace("\\", "/"), bytes=p.stat().st_size, sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted(RUN.rglob("*")) if p.is_file() and "__pycache__" not in p.parts and p.name not in {"artifact_manifest.json", "delivery_receipt.json"}]
    (RUN / "artifact_manifest.json").write_text(json.dumps(entries, indent=2), encoding="utf-8")
    receipt = dict(checked_at=now(), verdict="needs_changes", code_sha="d56a1ed306d975be408a2f6f8fbe3e905d940643", material_sha="ad122224b02ec16194e03f937b02a218ff6faaa5", review_worktree=str(ROOT), report_sha256=hashlib.sha256(report.read_bytes()).hexdigest(), artifact_manifest_sha256=hashlib.sha256((RUN / "artifact_manifest.json").read_bytes()).hexdigest(), source_proof_sha256=hashlib.sha256((RUN / "author_raw_and_source_proof.json").read_bytes()).hexdigest(), manifest_entry_count=len(entries), exclusions=["artifact_manifest.json", "delivery_receipt.json", "__pycache__"], secret_matches=len(findings), fixture_data=True, human_labels=0, production_0021="not_run", push=False)
    (RUN / "delivery_receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps(dict(sealed_files=len(entries), secret_matches=len(findings))))
    assert not findings


if __name__ == "__main__":
    base = connection()
    if sys.argv[1] == "cbm":
        cbm()
    elif sys.argv[1] == "prepare":
        prepare(base)
    elif sys.argv[1] == "seal":
        record("seal", ["review_runner.py", "seal", "actual-value scan then exact raw manifest"], ROOT, now(), 0, 0)
        seal()
    else:
        receipt = json.loads((RUN / "database_receipt.json").read_text())
        scoped = base.set(database=receipt["database"]).update_query_dict(dict(options=f"-csearch_path={receipt['schema']} -cstatement_timeout=15000 -clock_timeout=5000"))
        environment = os.environ.copy()
        environment.update(TEST_DATABASE_URL=scoped.render_as_string(hide_password=False), DIANZI_TEST_RUN_ID="r11_assessment_review1_20261016", PYTHONPATH=str(ROOT / "backend/src"))
        SECRETS.add(environment["TEST_DATABASE_URL"])
        raise SystemExit(run(sys.argv[1], [str(PYTHON), *sys.argv[2:]], ROOT / "backend", environment, 240))
