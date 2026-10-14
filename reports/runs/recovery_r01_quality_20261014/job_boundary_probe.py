"""真实专库负例：逻辑时钟用于租约边界，不计为持续运行，所有探针事务回滚。"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import create_engine

from ai_intel.infrastructure.outbox import enqueue_job
from ai_intel.workers.jobs import JobLeaseLostError, claim_next_job, complete_job, schedule_retry_or_fail

root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root))
from scripts.dev import require_isolated_test_database

private = subprocess.run(
    ["wsl.exe", "-d", "Ubuntu-22.04", "-u", "root", "--exec", "python3", "-c",
     "import pathlib,sys;sys.stdout.write(pathlib.Path(sys.argv[1]).read_text())",
     "/tmp/dianzi-docker-static-r01-20261014/runtime/test-services-r01_quality_20261014/connection.json"],
    capture_output=True, text=True, check=True, timeout=10,
)
configuration = json.loads(private.stdout)
assert configuration["DIANZI_TEST_RUN_ID"] == "r01_quality_20261014"
for key in ("TEST_DATABASE_URL", "DIANZI_TEST_RUN_ID"):
    os.environ[key] = configuration[key]
configuration.clear()
private = None
database_url = require_isolated_test_database()
engine = create_engine(database_url, connect_args={"connect_timeout": 5, "options": "-c statement_timeout=5000 -c lock_timeout=1000"})
now = datetime.now(UTC)
with engine.connect() as connection:
    transaction = connection.begin()
    try:
        retry_type = "quality_backoff_probe_" + uuid.uuid4().hex
        retry_id = enqueue_job(connection, None, retry_type, b"explicit synthetic probe", now)
        assert claim_next_job(connection, "quality_worker_a", now, retry_type) is not None
        assert schedule_retry_or_fail(connection, retry_id, "quality_worker_a", False, now) == "retry_wait"
        immediate_claim = claim_next_job(connection, "quality_worker_b", now, retry_type)
        lease_type = "quality_expired_lease_probe_" + uuid.uuid4().hex
        lease_id = enqueue_job(connection, None, lease_type, b"explicit synthetic lease probe", now)
        assert claim_next_job(connection, "quality_worker_c", now, lease_type) is not None
        try:
            complete_job(connection, lease_id, "quality_worker_c", "succeeded", now + timedelta(seconds=61))
            expired_completion_accepted = True
        except JobLeaseLostError:
            expired_completion_accepted = False
    finally:
        transaction.rollback()
engine.dispose()
print(json.dumps({"immediate_retry_claimed": immediate_claim is not None,
                  "expired_completion_accepted": expired_completion_accepted,
                  "expected_immediate_retry_claimed": False,
                  "expected_expired_completion_accepted": False,
                  "transaction_rolled_back": True,
                  "mode": "real PostgreSQL with explicit synthetic logical clock"}))
raise SystemExit(1 if immediate_claim is not None or expired_completion_accepted else 0)
