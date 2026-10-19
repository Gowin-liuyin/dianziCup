"""Record isolated review commands without copying or exposing private credentials."""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from xml.etree import ElementTree
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
PYTHON = sys.executable
ZONE = ZoneInfo("Asia/Shanghai")
environment = os.environ.copy()
environment["PYTHONPATH"] = os.pathsep.join((str(ROOT / "backend/src"), str(ROOT / "backend"), str(ROOT / "backend/tests/integration")))
private = {}
database_name = None
borrowed_database = None


def record(name, command, cwd=ROOT, env=None):
    name = os.environ.get("R07_REVIEW_RUN_LABEL", "initial_7dae") + "_" + name
    started = datetime.now(ZONE).isoformat()
    result = subprocess.run(command, cwd=cwd, env=env or environment, capture_output=True, text=True, encoding="utf-8", errors="replace")
    output = result.stdout + result.stderr
    for secret in (private.get("TEST_DATABASE_URL"), private.get("postgres_password"), environment.get("TEST_DATABASE_URL")):
        if secret:
            output = output.replace(secret, "[redacted test connection]")
    receipt = {"started_at": started, "completed_at": datetime.now(ZONE).isoformat(), "command": command, "cwd": str(cwd), "exit_code": result.returncode, "isolated_database": database_name, "borrowed_schema_isolated_database": borrowed_database, "tested_tree_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()}
    if "--junitxml" in command:
        path = Path(command[command.index("--junitxml") + 1])
        if path.exists():
            cases = ElementTree.parse(path).findall(".//testcase")
            receipt.update(tests=len(cases), failed=sum(case.find("failure") is not None for case in cases), errors=sum(case.find("error") is not None for case in cases), skipped=sum(case.find("skipped") is not None for case in cases))
    (RUN / (name + ".log")).write_text(output, encoding="utf-8")
    (RUN / (name + ".command.json")).write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=False))
    print(output[-4500:])
    return result.returncode


def main():
    global private, database_name, borrowed_database
    mode = sys.argv[1]
    if mode.startswith("cbm"):
        project = "r07-input-review1-src-20261016"
        base = "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp"
        commands = {
            "cbm_help": ["--help"],
            "cbm_index": ["index_repository", "--repo-path", "/mnt/d/wt/r07-input-review1/backend/src", "--name", project, "--mode", "fast"],
            "cbm_schema": ["get_graph_schema", "--project", project],
            "cbm_architecture": ["get_architecture", "--project", project, "--aspects", "all"],
            "cbm_trace": ["trace_path", "--project", project, "--function-name", project + ".ai_intel.enrichment.model_fields.extract_model_dimension", "--direction", "both", "--format", "json", "--depth", "4", "--limit", "100"],
            "cbm_loader_trace": ["trace_path", "--project", project, "--function-name", project + ".ai_intel.enrichment.taxonomy_inputs.load_taxonomy_catalogue", "--direction", "both", "--format", "json", "--depth", "4", "--limit", "100"],
            "cbm_validator_trace": ["trace_path", "--project", project, "--function-name", project + ".ai_intel.enrichment.field_sources.validate_field_candidate", "--direction", "both", "--format", "json", "--depth", "4", "--limit", "100"],
        }
        return record(mode, ["wsl.exe", "-u", "root", "--exec", "env", "CBM_CACHE_DIR=/tmp/dianzi-cbm-r07-input-review1-20261016", "CBM_ALLOWED_ROOT=/mnt/d/wt/r07-input-review1/backend/src", base, "cli", "--json", *commands[mode]])
    if mode == "full_schema":
        return record(mode, [PYTHON, str(RUN / "replay_full_schema.py")])
    if mode == "caller_audit":
        return record(mode, [PYTHON, str(RUN / "audit_callers.py")])
    if mode == "material_diff":
        return record(mode, ["git", "diff", "--check", "7dae1d82363d8459f3546fee4b92137559dcb5aa", "eb6daced5f2467dc56ade15857e60a1af9486db0"])
    if mode == "prepare_resource":
        return record(mode, [PYTHON, str(RUN / "prepare_resource_copies.py")])
    if mode == "verify_fix2_material":
        return record(mode, [PYTHON, str(RUN / "verify_fix2_material.py")])
    if mode in ("integration", "probe_pg", "graph_pg", "publication_pg", "graph_pg_copies", "publication_pg_copies", "graph_pg_copies_retry"):
        private = json.loads(subprocess.check_output(["wsl.exe", "-u", "root", "--exec", "cat", "/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json"], stderr=subprocess.PIPE))
        original = make_url(private["TEST_DATABASE_URL"])
        assert original.username.startswith("test_") and original.database.startswith("test_dianzi_")
        admin = create_engine(original.set(database="postgres"), isolation_level="AUTOCOMMIT")
        if mode in ("graph_pg", "publication_pg"):
            run_id = "r06_catalog_r10_graph_20261016"
            borrowed_database = "test_dianzi_" + run_id
            with admin.connect() as connection:
                owner = connection.scalar(text("SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname=:name"), {"name": borrowed_database})
                assert owner == original.username
            selected_database = borrowed_database
        else:
            run_id = "r07_input_review1_" + datetime.now(ZONE).strftime("%m%d_%H%M%S") + "_" + uuid4().hex[:5]
            database_name = "test_dianzi_" + run_id
            with admin.connect() as connection:
                connection.execute(text('CREATE DATABASE "' + database_name + '"'))
            selected_database = database_name
        admin.dispose()
        environment["TEST_DATABASE_URL"] = original.set(database=selected_database).render_as_string(hide_password=False)
        environment["DIANZI_TEST_RUN_ID"] = run_id
        if "_copies" in mode:
            environment["PYTHONPATH"] = os.pathsep.join((str(RUN / "resource_copies"), environment["PYTHONPATH"]))
    paths = {
        "unit": ["tests/unit/test_r07_input_capabilities.py"],
        "contract": ["tests/contract/test_r07_input_selection_codec.py"],
        "security": ["tests/security/test_r07_input_capabilities_boundary.py"],
        "integration": ["tests/integration/test_r07_input_capabilities_pg.py"],
        "regression": ["tests/unit/test_r07_model_fields.py", "tests/unit/test_r07_single_model_dimension.py", "tests/unit/test_r07_model_field_root_causes.py"],
        "fieldset": ["tests/unit/test_r07_enrichment_contracts.py", "tests/unit/test_r07_public_signals.py", "tests/unit/test_r10_relation_polarity.py"],
        "graph": ["tests/unit/test_r10_evidence_graph.py", "tests/contract/test_r10_graph_contract.py", "tests/security/test_r10_graph_boundary.py"],
        "graph_pg": ["tests/integration/test_r10_evidence_graph_pg.py", "tests/integration/test_r10_graph_validity_pg.py", "tests/integration/test_r10_graph_source_coverage_pg.py", "tests/integration/test_r10_graph_fix2_pg.py"],
        "publication_pg": ["tests/integration/test_r07_enrichment_publication_pg.py", "tests/integration/test_r07_publication_rule_provenance_pg.py", "tests/integration/test_r07_publication_acl_lock_fix_pg.py"],
        "graph_pg_copies": [str(RUN / "resource_copies" / name) for name in ("test_r10_evidence_graph_pg.py", "test_r10_graph_validity_pg.py", "test_r10_graph_source_coverage_pg.py", "test_r10_graph_fix2_pg.py")],
        "graph_pg_copies_retry": [str(RUN / "resource_copies" / name) for name in ("test_r10_evidence_graph_pg.py", "test_r10_graph_validity_pg.py", "test_r10_graph_source_coverage_pg.py", "test_r10_graph_fix2_pg.py")],
        "publication_pg_copies": [str(RUN / "resource_copies" / name) for name in ("test_r07_enrichment_publication_pg.py", "test_r07_publication_rule_provenance_pg.py", "test_r07_publication_acl_lock_fix_pg.py")],
        "probe": [str(RUN / "test_review_probe.py")],
        "probe_pg": [str(RUN / "test_review_probe_pg.py")],
    }
    if mode in paths:
        label = os.environ.get("R07_REVIEW_RUN_LABEL", "initial_7dae")
        extra = ["--lf"] if mode == "graph_pg_copies_retry" else []
        return record(mode, [PYTHON, "-m", "pytest", "-q", *paths[mode], *extra, "--no-cov", "--junitxml", str(RUN / (label + "_" + mode + ".xml"))], ROOT / "backend")
    if mode == "static":
        files = ["src/ai_intel/enrichment/evidence_selection.py", "src/ai_intel/enrichment/taxonomy_inputs.py", "src/ai_intel/enrichment/model_fields.py", "src/ai_intel/enrichment/field_sources.py", "tests/unit/test_r07_input_capabilities.py", "tests/contract/test_r07_input_selection_codec.py", "tests/security/test_r07_input_capabilities_boundary.py", "tests/integration/test_r07_input_capabilities_pg.py"]
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
        codes = [record("static_ruff", [PYTHON, "-m", "ruff", "check", *files], ROOT / "backend"), record("static_format", [PYTHON, "-m", "ruff", "format", "--check", *files], ROOT / "backend"), record("static_mypy", [PYTHON, "-m", "mypy", *files[:4]], ROOT / "backend"), record("source_diff_check", ["git", "diff", "--check", "7dae1d82^", head, "--", "backend"])]
        return next((code for code in codes if code), 0)
    raise ValueError("unsupported mode")


if __name__ == "__main__":
    raise SystemExit(main())
