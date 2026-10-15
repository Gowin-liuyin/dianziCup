"""Run recorded-source tests against one authorized private test database."""

import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

run_root = Path(__file__).resolve().parent
repo_root = run_root.parents[2]
private = json.loads(Path("/tmp/dianzi-r04_sources_20261015/connection.json").read_bytes())
base = make_url(private["TEST_DATABASE_URL"])
assert base.host == "127.0.0.1" and base.port == 25432
assert base.database == "test_dianzi_r04_sources_20261015"
assert base.username and base.username.startswith("test_")
database_name = "test_dianzi_r04_source_documents_20261015"
admin = create_engine(base.set(database="postgres"), isolation_level="AUTOCOMMIT")
with admin.connect() as connection:
    if not connection.scalar(
        text("SELECT 1 FROM pg_database WHERE datname=:name"), {"name": database_name}
    ):
        connection.execute(text('CREATE DATABASE "test_dianzi_r04_source_documents_20261015"'))
admin.dispose()
url = base.set(database=database_name)
environment = {
    key: value
    for key, value in os.environ.items()
    if not any(word in key.upper() for word in ("KEY", "TOKEN", "PASSWORD", "SECRET"))
}
environment["TEST_DATABASE_URL"] = url.render_as_string(hide_password=False)
environment["DIANZI_TEST_RUN_ID"] = "r04_source_documents_20261015"
environment["PYTHONPATH"] = str(repo_root / "backend/src")
environment.pop("VIRTUAL_ENV", None)
private_root = Path("/tmp/dianzi-r04_source_documents_20261015")
private_root.mkdir(mode=0o700, exist_ok=True)
private_file = private_root / "connection.json"
private_file.write_text(
    json.dumps(
        {
            "TEST_DATABASE_URL": environment["TEST_DATABASE_URL"],
            "DIANZI_TEST_RUN_ID": environment["DIANZI_TEST_RUN_ID"],
        }
    ),
    encoding="utf-8",
)
private_file.chmod(0o600)
name = sys.argv[1]
command = [
    sys.executable,
    "-m",
    "pytest",
    *sys.argv[2:],
    "--no-cov",
    "-q",
    f"--junitxml={run_root / (name + '.xml')}",
]
started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
clock = time.monotonic()
completed = subprocess.run(
    command,
    cwd=repo_root / "backend",
    env=environment,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    timeout=300,
    check=False,
)
output = completed.stdout
credential_values = [environment["TEST_DATABASE_URL"], base.password or ""]
password = base.password or ""
fragments = {password[index : index + 8] for index in range(max(0, len(password) - 7))}
matches = []
for credential in credential_values:
    if credential and credential.encode() in output:
        matches.append("full_value")
        output = output.replace(credential.encode(), b"[redacted test credential]")
for fragment in fragments:
    if fragment.encode() in output:
        matches.append("fragment")
        output = output.replace(fragment.encode(), b"[redacted test credential fragment]")
(run_root / (name + ".log")).write_bytes(output)
report = run_root / (name + ".xml")
if report.exists():
    content = report.read_bytes()
    for credential in credential_values:
        if credential and credential.encode() in content:
            matches.append("junit_full_value")
            content = content.replace(credential.encode(), b"[redacted test credential]")
    for fragment in fragments:
        if fragment.encode() in content:
            matches.append("junit_fragment")
            content = content.replace(fragment.encode(), b"[redacted test credential fragment]")
    report.write_bytes(content)
receipt = {
    "started_at": started,
    "ended_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
    "duration_seconds": round(time.monotonic() - clock, 3),
    "exit_code": completed.returncode,
    "command": command,
    "cwd": str(repo_root / "backend"),
    "database_name": database_name,
    "secret_output_matches": matches,
    "data_mode": "recorded isolated fixture integration; not live",
}
(run_root / (name + ".receipt.json")).write_text(
    json.dumps(receipt, indent=2) + "\n", encoding="utf-8"
)
print(json.dumps(receipt))
raise SystemExit(completed.returncode)
