"""Reuse authorized private connections and write only new Must1 command receipts."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from importlib import import_module
from pathlib import Path

from sqlalchemy.engine import make_url

FIX_RUN = Path(__file__).resolve().parent
ROOT = FIX_RUN.parents[2]
ORIGINAL_RUN = ROOT / "reports/runs/recovery_r12_hybrid_retrieval_20261016"
sys.path.insert(0, str(ORIGINAL_RUN))
run_checks = import_module("run_checks")


def main() -> int:
    run_checks.RUN = FIX_RUN
    run_checks.ROOT = ROOT
    if "--services" in sys.argv:
        sys.argv.remove("--services")
        captured = subprocess.run(
            [
                "wsl",
                "-d",
                "Ubuntu-22.04",
                "-u",
                "root",
                "--",
                "cat",
                "/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json",
            ],
            capture_output=True,
            timeout=15,
        )
        if captured.returncode:
            return 4
        connection = json.loads(captured.stdout)
        url = make_url(connection["TEST_DATABASE_URL"])
        if (url.host, url.port, url.database) != ("127.0.0.1", 25432, "test_dianzi_r01_20261014"):
            return 4
        os.environ["TEST_DATABASE_URL"] = url.set(
            database="test_dianzi_r12_hybrid_20261016"
        ).render_as_string(hide_password=False)
        os.environ["DIANZI_TEST_RUN_ID"] = "r12_hybrid_20261016"
        os.environ["R05_SEMANTIC_CACHE"] = "C:/Users/yinha/.codex/cache/dianzi/r05-semantic-runtime"
        os.environ["R12_EVIDENCE_DIR"] = str(FIX_RUN / "synthetic_source_blobs")
        os.environ["R12_OPENSEARCH_URL"] = "http://127.0.0.1:29200"
    return run_checks.execute(sys.argv[1], [str(run_checks.PYTHON), *sys.argv[2:]])


if __name__ == "__main__":
    raise SystemExit(main())
