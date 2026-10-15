"""Only the new isolated TTL test DB is passed in-memory to the target tests."""

import os
from pathlib import Path
import subprocess
import sys

from prepare_pg import RUN_ID, test_connection

try:
    environment = dict(os.environ)
    environment["TEST_DATABASE_URL"] = test_connection()
    environment["DIANZI_TEST_RUN_ID"] = RUN_ID
    environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[3] / "backend" / "src")
    result = subprocess.run([sys.executable, "-m", "pytest", "tests/integration/test_r08_cache_ttl_fix1_pg.py",
        "--no-cov", "-q", "--junitxml=../reports/runs/recovery_r08_cache_ttl_fix1_20261016/pg.xml"],
        cwd=Path(__file__).resolve().parents[3] / "backend", env=environment, check=False)
    raise SystemExit(result.returncode)
except Exception:
    print("blocked: isolated TTL PostgreSQL test runner unavailable; no connection details emitted")
    raise SystemExit(2) from None
