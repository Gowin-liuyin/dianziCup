"""Inspect and clean only the exact owned DB from the partial probe observation."""

import json
import re
import subprocess
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool

RUN = Path(__file__).resolve().parent
row = json.loads((RUN / "same_probe_observation.json").read_bytes())
database = row["database"]
assert re.fullmatch(r"test_dianzi_r18_rev_fix2_[0-9a-f]{32}", database)
receipt = {"started_at": datetime.now().astimezone().isoformat(), "database": database,
           "initial_probe_business_status": row["status"], "initial_failure":
           "DROP DATABASE statement_timeout after schema/session zero; runner receipt not finalized",
           "original_runner_raw_receipt": "not_created_due_to_cleanup_exception"}
decoded = subprocess.run([
    "C:/Users/yinha/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/powershell/pwsh.exe",
    "-NoProfile", "-Command", "$r18Protected=Get-Content -LiteralPath 'D:/dianzi-private/test-runtime-resource-reference-20261016.dpapi' -Raw; "
    "$r18Clear=$r18Protected | ConvertTo-SecureString | ConvertFrom-SecureString -AsPlainText; [Console]::Write($r18Clear)",
], capture_output=True, timeout=15, check=True)
original = make_url(json.loads(decoded.stdout)["TEST_DATABASE_URL"])
assert original.host == "127.0.0.1" and original.port == 25432
assert original.username and re.fullmatch(r"test_[a-z0-9_]+", original.username)
engine = create_engine(original.set(database="postgres"), isolation_level="AUTOCOMMIT",
    hide_parameters=True, poolclass=NullPool,
    connect_args={"connect_timeout": 5, "options": "-c statement_timeout=12000"})
status = 0
try:
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT current_user")) == original.username
        exists = connection.scalar(text("SELECT EXISTS(SELECT 1 FROM pg_database WHERE datname=:name)"), {"name": database})
        remaining = connection.scalar(text("SELECT count(*) FROM pg_stat_activity WHERE datname=:name"), {"name": database})
        receipt.update({"exists_before": exists, "sessions_before": remaining})
        if remaining != 0:
            raise RuntimeError("owned DB sessions still present; no forced termination")
        if exists:
            connection.exec_driver_sql(f'DROP DATABASE "{database}"')
        receipt["exists_after"] = connection.scalar(text("SELECT EXISTS(SELECT 1 FROM pg_database WHERE datname=:name)"), {"name": database})
        assert not receipt["exists_after"]
except Exception as failure:
    receipt["failure_type"] = type(failure).__name__
    status = 1
finally:
    engine.dispose()
receipt.update({"ended_at": datetime.now().astimezone().isoformat(), "exit_code": status,
                "pool": "NullPool; disposed", "shared_sessions_terminated": False})
(RUN / "initial_cleanup_receipt.json").write_text(json.dumps(receipt, indent=2)+"\n", encoding="utf-8")
print(json.dumps({"exit_code": status, "exists_after": receipt.get("exists_after"),
                  "sessions_before": receipt.get("sessions_before")}))
raise SystemExit(status)
