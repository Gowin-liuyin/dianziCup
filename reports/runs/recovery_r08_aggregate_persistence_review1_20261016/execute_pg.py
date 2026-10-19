"""Run only authorized PostgreSQL checks using the review database."""

import os
from pathlib import Path
import subprocess
import sys

from prepare_pg import DATABASE_NAME, RUN_ID, test_connection

try:
    environment = dict(os.environ)
    environment["TEST_DATABASE_URL"] = test_connection().set(database=DATABASE_NAME).render_as_string(hide_password=False)
    environment["DIANZI_TEST_RUN_ID"] = RUN_ID
    root = Path(__file__).resolve().parents[3]
    environment["PYTHONPATH"] = str(root / "backend" / "src")
    files = sys.argv[1:] or ["tests/integration/test_r08_aggregate_persistence_pg.py"]
    result = subprocess.run([sys.executable, "-m", "pytest", *files, "--no-cov", "-q",
        "--junitxml=../reports/runs/recovery_r08_aggregate_persistence_review1_20261016/pg.xml"],
        cwd=root / "backend", env=environment, check=False)
    raise SystemExit(result.returncode)
except Exception as failure:
    print("PG review runner blocked; safe exception type=" + type(failure).__name__)
    raise SystemExit(2) from None
