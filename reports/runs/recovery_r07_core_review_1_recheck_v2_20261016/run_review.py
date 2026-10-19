"""Execute bounded independent checks and seal commands without connection values."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
RUN_ID = "r06_catalog_r07_core_recheck_v2_20261016"
DATABASE = "test_dianzi_" + RUN_ID


def now() -> str:
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT)


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def audit() -> None:
    manifest_path = "reports/runs/recovery_r07_core_fix1_20261015/artifact_manifest.json"
    manifest_bytes = git("show", "cb34097898b412390ee7e119d0d5c2c90d090673:" + manifest_path)
    manifest = json.loads(manifest_bytes)
    observed_hash = hashlib.sha256(manifest_bytes).hexdigest()
    assert observed_hash == "48cbfb075841db59358eb52634a5c159ef8b5d822c5e33a03ee597677c111cc6"
    artifacts = []
    for item in manifest["artifacts"]:
        blob = git("show", "cb34097898b412390ee7e119d0d5c2c90d090673:" + item["path"])
        digest = hashlib.sha256(blob).hexdigest()
        artifacts.append({"path": item["path"], "bytes": len(blob), "sha256": digest, "matches": digest == item["sha256"] and len(blob) == item["bytes"], "git_blob_id": git("rev-parse", "cb34097898b412390ee7e119d0d5c2c90d090673:" + item["path"]).decode().strip()})
    assert len(artifacts) == 30 and all(item["matches"] for item in artifacts)
    inputs = ["AGENTS.md", "docs/plan/00_execution_map.md", "docs/plan/03_data_contracts.md", "docs/plan/04_workflows_and_algorithms.md", "docs/plan/05_api_and_tool_contracts.md", "docs/plan/06_testing_and_evaluation.md", "docs/plan/11_full_delivery_recovery_20261014.md", "docs/plan/12_recovery_task_cards_20261014.md", "docs/tasks/T13_community_repository_connectors.md", "docs/tasks/T19_structured_enrichment.md", "docs/tasks/T20_claim_extraction.md", "docs/tasks/T22_research_and_document_links.md", "docs/tasks/T23_poc_scores_impact.md", "docs/tasks/T41_sources_events_ui.md", "docs/decisions/CR-R07.md", "docs/decisions/CR-R07_enrichment_candidate_seam.md", "docs/decisions/CR-R07_typed_signal_claim_v3.md", "progress/task_state.json", "progress/context_handoff.md", "reports/tasks/R07-core.md", "reports/tasks/R07-core-fix1.md"]
    input_receipts = [{"path": path, "git_sha256": hashlib.sha256(git("show", "HEAD:" + path)).hexdigest()} for path in inputs]
    write_json(RUN / "author_blob_audit.json", {"recorded_at": now(), "manifest_sha256": observed_hash, "artifacts": artifacts, "inputs": input_receipts, "code_full_freeze_diff": git("diff", "--name-only", "ce1da8811495f1ea1de538c67cb12b16e6d8a280", "cb34097898b412390ee7e119d0d5c2c90d090673", "--", "backend/src", "backend/tests", "contracts").decode(), "baseline_diff": git("diff", "--stat", "74d8e9ba8b49360ca90ade390f7b6c00cd40b815", "ce1da8811495f1ea1de538c67cb12b16e6d8a280", "--", "backend/src", "backend/tests", "contracts").decode()})


def execute(label: str, mode: str) -> int:
    started = now()
    write_json(RUN / (label + ".start.json"), {"label": label, "mode": mode, "started_at": started, "full_sha": git("rev-parse", "HEAD").decode().strip()})
    environment = dict(os.environ)
    for name in ("TEST_DATABASE_URL", "TEST_REDIS_URL", "DIANZI_TEST_RUN_ID"):
        environment.pop(name, None)
    environment.update(PYTHONIOENCODING="utf-8", PYTHONPATH=os.pathsep.join((str(ROOT / "backend/src"), str(ROOT / "backend"), str(ROOT / "backend/tests/integration"))))
    sensitive_values: list[str] = []
    if mode in {"pg", "independent_pg"}:
        private = subprocess.run(["wsl.exe", "-d", "Ubuntu-22.04", "-u", "root", "--exec", "cat", "/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json"], capture_output=True, check=True)
        url = make_url(json.loads(private.stdout)["TEST_DATABASE_URL"])
        assert url.host in {"127.0.0.1", "localhost"} and url.database.startswith("test_dianzi_")
        assert url.username.startswith("test_") and url.port != 5432
        sensitive_values = [url.render_as_string(hide_password=False), str(url.password)]
        base = create_engine(url, isolation_level="AUTOCOMMIT", connect_args={"connect_timeout": 5})
        try:
            with base.connect() as connection:
                assert connection.scalar(text("SELECT 1")) == 1
                if not connection.scalar(text("SELECT 1 FROM pg_database WHERE datname=:name"), {"name": DATABASE}):
                    connection.execute(text('CREATE DATABASE "' + DATABASE + '"'))
        finally:
            base.dispose()
        environment.update(TEST_DATABASE_URL=url.set(database=DATABASE).render_as_string(hide_password=False), DIANZI_TEST_RUN_ID=RUN_ID)
        sensitive_values.append(environment["TEST_DATABASE_URL"])
        from scripts.dev import require_isolated_test_database
        require_isolated_test_database(environment)
    changed = ["src/ai_intel/domain/enrichment_values.py", "src/ai_intel/knowledge/persistence.py", "tests/contract/test_r07_signal_schema_boundaries.py", "tests/integration/test_r07_literature_target_scope_pg.py"]
    options = {
        "unit": ["pytest", "tests/contract/test_r07_signal_schema_boundaries.py", "tests/contract/test_r07_signal_claim_values.py", "tests/contract/test_r02_value_contract.py", "tests/unit/test_r02_knowledge_publication_contract.py", "tests/unit/test_r07_enrichment_contracts.py", "-o", "addopts=", "-q"],
        "pg": ["pytest", "tests/integration/test_r07_literature_target_scope_pg.py", "tests/integration/test_r07_signal_claim_values_pg.py", "tests/integration/test_r06_catalog_documents_pg.py", "-o", "addopts=", "-q"],
        "independent_schema": ["pytest", str(RUN / "test_independent_schema.py"), "-p", "tests.conftest", "-o", "addopts=", "-q"],
        "independent_pg": ["pytest", str(RUN / "test_independent_target_scope.py"), "-p", "tests.conftest", "-o", "addopts=", "-q"],
        "independent_pg_collect": ["pytest", str(RUN / "test_independent_target_scope.py"), "-p", "tests.conftest", "-o", "addopts=", "--collect-only", "-q"],
        "ruff": ["ruff", "check", *changed],
        "format": ["ruff", "format", "--check", *changed],
        "mypy": ["mypy", "src"],
    }
    argv = [sys.executable, "-m", *options[mode]]
    is_test = mode in {"unit", "pg", "independent_schema", "independent_pg"}
    if is_test:
        argv.append("--junitxml=" + str(RUN / (label + ".xml")))
    result = subprocess.run(argv, cwd=ROOT / "backend", env=environment, capture_output=True, timeout=600)
    output = result.stdout + result.stderr
    for value in sensitive_values:
        output = output.replace(value.encode(), b"[redacted test connection or credential]")
    (RUN / (label + ".log")).write_bytes(output)
    counts = None
    if is_test and (RUN / (label + ".xml")).exists():
        report = RUN / (label + ".xml")
        content = report.read_bytes()
        for value in sensitive_values:
            content = content.replace(value.encode(), b"[redacted test connection or credential]")
        report.write_bytes(content)
        cases = ET.fromstring(content).findall(".//testcase")
        counts = {"tests": len(cases), "failures": sum(case.find("failure") is not None for case in cases), "errors": sum(case.find("error") is not None for case in cases), "skipped": sum(case.find("skipped") is not None for case in cases)}
    write_json(RUN / (label + ".json"), {"argv": argv, "cwd": str(ROOT / "backend"), "started_at": started, "ended_at": now(), "exit_code": result.returncode, "counts": counts, "code_sha": "ce1da8811495f1ea1de538c67cb12b16e6d8a280", "full_sha": git("rev-parse", "HEAD").decode().strip(), "database": DATABASE if mode in {"pg", "independent_pg"} else None, "run_id": RUN_ID if mode in {"pg", "independent_pg"} else None, "product_tree": git("status", "--porcelain", "--", "backend/src", "backend/tests", "contracts").decode().strip() or "clean", "scope": "independent fixture/real UUID-isolated PG only; no external source, model or asset calls"})
    print(json.dumps({"label": label, "exit_code": result.returncode, "counts": counts}))
    return result.returncode


if __name__ == "__main__":
    if sys.argv[1] == "audit":
        audit()
        print("30 author Git blobs match frozen manifest")
    else:
        try:
            raise SystemExit(execute(*sys.argv[1:]))
        except Exception as error:
            label, mode = sys.argv[1:]
            start_receipt = json.loads((RUN / (label + ".start.json")).read_text(encoding="utf-8"))
            details = {**start_receipt, "ended_at": now(), "exit_code": 1, "phase": "check bootstrap", "error_type": type(error).__name__, "tests_executed": 0, "status": "blocked", "connection_values_recorded": False}
            write_json(RUN / (label + ".json"), details)
            (RUN / (label + ".log")).write_text("Bootstrap blocked: " + type(error).__name__ + "; connection values suppressed\n", encoding="utf-8", newline="\n")
            print(json.dumps({"label": label, "exit_code": 1, "status": "blocked", "error_type": type(error).__name__}))
            raise SystemExit(1) from None
