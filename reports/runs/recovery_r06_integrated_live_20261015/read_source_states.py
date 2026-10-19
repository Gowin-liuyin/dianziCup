"""Read only safe job metadata from this one isolated live DB."""

import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

RUN = Path(__file__).resolve().parent
private = subprocess.run(["wsl.exe", "-d", "Ubuntu-22.04", "-u", "root", "--exec", "cat", "/tmp/dianzi-r04-live-20261015/private/runtime_8f6bd9.json"], capture_output=True, text=True, check=True, timeout=10)
configuration = json.loads(private.stdout)
url = make_url(configuration["environment"]["DATABASE_URL"]).set(database="test_dianzi_r06_integrated_live_20261015")
assert url.host in {"localhost", "127.0.0.1"}
engine = create_engine(url, connect_args={"connect_timeout": 3, "options": "-c statement_timeout=3000"})
with engine.connect() as connection:
    rows = []
    for row in connection.execute(text("select j.job_id,j.status,j.error_code,j.attempt_count,j.created_at,j.finished_at,j.idempotency_key,p.payload from job_runs j join job_payloads p on p.job_id=j.job_id where j.job_type='collect_public_source_page' order by j.created_at")).mappings():
        value = dict(row)
        value["request"] = json.loads(bytes(value.pop("payload")))
        rows.append(value)
engine.dispose()
receipt = {"observed_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"), "code_sha": "1156b2ed6616e3a4297215c2893d2cbe633f5215", "jobs": rows, "read_only": True}
(RUN / "source_jobs_metadata.json").write_text(json.dumps(receipt, indent=2, default=str) + "\n", encoding="utf-8")
print(json.dumps({"observed_at": receipt["observed_at"], "jobs": [{"source_kind": item["request"]["source_kind"], "status": item["status"], "error_code": item["error_code"], "attempt_count": item["attempt_count"]} for item in rows]}))
