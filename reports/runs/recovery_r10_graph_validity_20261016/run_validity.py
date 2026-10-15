"""每次检查另存实际输出，不覆盖原作者或 reviewer 材料。"""

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent


def main():
    label, *arguments = sys.argv[1:]
    assert label.replace("_", "").isalnum()
    assert not (RUN / (label + ".log")).exists()
    private = json.loads(subprocess.check_output(["wsl", "-d", "Ubuntu-22.04", "-u", "root", "--", "cat", "/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json"], text=True))
    source = make_url(private["TEST_DATABASE_URL"])
    assert source.host == "127.0.0.1" and source.port == 25432 and source.username.startswith("test_")
    database = "test_dianzi_r06_catalog_r10_graph_20261016"
    environment = dict(os.environ, PYTHONPATH=str(ROOT / "backend/src") + os.pathsep + str(ROOT / "backend/tests/integration"), DIANZI_TEST_RUN_ID="r06_catalog_r10_graph_20261016", TEST_DATABASE_URL=source.set(database=database).render_as_string(hide_password=False))
    environment["R10_OBSERVATIONS_PATH"] = str(RUN / (label + "_http.jsonl"))
    command = [sys.executable, "-m", "pytest", "-o", "addopts=", *arguments, "-q", "--junitxml=" + str(RUN / (label + ".xml"))]
    now = lambda: datetime.now(timezone(timedelta(hours=8))).isoformat()
    started = now()
    result = subprocess.run(command, cwd=ROOT / "backend", env=environment, capture_output=True, text=True, encoding="utf-8", errors="replace")
    output = (result.stdout + result.stderr).replace(environment["TEST_DATABASE_URL"], "[redacted connection]").replace(source.password, "[redacted credential]")
    (RUN / (label + ".log")).write_text(output, encoding="utf-8")
    receipt = {"command": command, "cwd": str(ROOT / "backend"), "started_at": started, "finished_at": now(), "exit_code": result.returncode, "database": database, "data_mode": "fixture", "baseline": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()}
    (RUN / (label + ".json")).write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"label": label, "exit_code": result.returncode}))
    print(output[-1400:])
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
