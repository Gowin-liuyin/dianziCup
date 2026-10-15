"""Keep each original fixture's database namespace and matching isolation marker."""

import json
import os
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
private = subprocess.run(["wsl.exe", "-d", "Ubuntu-22.04", "-u", "root", "--exec", "cat", "/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json"], capture_output=True, check=True)
url = make_url(json.loads(private.stdout)["TEST_DATABASE_URL"])
assert url.host in {"localhost", "127.0.0.1"} and url.port == 25432
run_id = "r07_execution_api_20261016"
environment = dict(os.environ, PYTHONIOENCODING="utf8", PYTHONPATH=str(ROOT / "backend/src"), DIANZI_TEST_RUN_ID=run_id, TEST_DATABASE_URL=url.set(database="test_dianzi_" + run_id).render_as_string(hide_password=False))
argv = [str(ROOT / "backend/.venv/Scripts/python.exe"), "-m", "pytest", "tests/integration/test_r11_default_readers_pg.py", "--no-cov", "-q", "--junitxml=" + str(RUN / "default_readers_pg_v2.xml")]
with (RUN / "default_readers_pg_v2.log").open("xb") as output:
    result = subprocess.run(argv, cwd=ROOT / "backend", env=environment, stdout=output, stderr=subprocess.STDOUT, timeout=240)
suites = ET.parse(RUN / "default_readers_pg_v2.xml").getroot().findall("testsuite")
receipt = {"started_at": started, "ended_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"), "cwd": str(ROOT / "backend"), "argv": argv, "exit_code": result.returncode, "junit": {field: sum(int(suite.attrib.get(field, 0)) for suite in suites) for field in ("tests", "failures", "errors", "skipped")}, "wire_calls": 0, "source_state": "current root API/worker WIP; no dependency/schema change since last static check"}
(RUN / "default_readers_pg_v2.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps(receipt))
raise SystemExit(result.returncode)
