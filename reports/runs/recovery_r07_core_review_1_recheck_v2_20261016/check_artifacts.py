"""Check exact private bytes and read only the dedicated review database after fixture cleanup."""

import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
DATABASE = "test_dianzi_r06_catalog_r07_core_recheck_v2_20261016"


def check():
    started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
    private = subprocess.run(["wsl.exe", "-d", "Ubuntu-22.04", "-u", "root", "--exec", "cat", "/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json"], capture_output=True, check=True)
    url = make_url(json.loads(private.stdout)["TEST_DATABASE_URL"])
    assert url.host in {"localhost", "127.0.0.1"} and url.username.startswith("test_")
    exact_private_values = [url.render_as_string(hide_password=False).encode(), url.set(database=DATABASE).render_as_string(hide_password=False).encode(), str(url.password).encode()]
    report = ROOT / "reports/reviews/recovery/G-C-R07-core-review-1-recheck-v2.md"
    paths = [report, *(path for path in RUN.rglob("*") if path.is_file() and "__pycache__" not in path.parts and path.name not in {"artifact_manifest.json", "seal.json"})]
    findings = []
    for path in paths:
        payload = path.read_bytes()
        if any(value and value in payload for value in exact_private_values):
            findings.append({"path": path.relative_to(ROOT).as_posix(), "kind": "private connection or credential bytes present"})
    assert not findings
    engine = create_engine(url.set(database=DATABASE), connect_args={"connect_timeout": 5, "options": "-c statement_timeout=15000 -c lock_timeout=5000"})
    try:
        with engine.connect() as connection:
            observed = connection.scalar(text("SELECT current_database()"))
            assert observed == DATABASE
            remaining = connection.scalar(text("SELECT count(*) FROM pg_namespace WHERE nspname LIKE 'test_r06_catalog_%'"))
            assert remaining == 0
    finally:
        engine.dispose()
    status = subprocess.check_output(["git", "status", "--porcelain", "--", "backend/src", "backend/tests", "contracts", "docs", "progress"], cwd=ROOT, text=True)
    assert not status.strip()
    result = {"started_at": started, "ended_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"), "exit_code": 0, "scanned_files": len(paths), "exact_private_value_findings": findings, "private_values_recorded": False, "database": DATABASE, "remaining_fixture_schemas": remaining, "product_test_contract_progress_tree": "clean"}
    (RUN / "artifact_safety_and_cleanup.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    return result
