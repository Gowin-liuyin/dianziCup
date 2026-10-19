"""Scan only the approved test resource's real DSN/password; never read production secrets."""

import html
import json
import subprocess
from datetime import datetime
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo

from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
captured = subprocess.run(["C:/Users/yinha/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/powershell/pwsh.exe", "-NoProfile", "-Command", "$taskProtected=Get-Content -LiteralPath 'D:/dianzi-private/test-runtime-resource-reference-20261016.dpapi' -Raw; $taskClear=$taskProtected | ConvertTo-SecureString | ConvertFrom-SecureString -AsPlainText; [Console]::Write($taskClear)"], capture_output=True, timeout=15, check=True)
original = make_url(json.loads(captured.stdout)["TEST_DATABASE_URL"])
assert original.drivername == "postgresql+psycopg" and (original.host, original.port, original.database) == ("127.0.0.1", 25432, "test_dianzi_r01_20261014")
assert original.username.startswith("test_") and original.password
values = {original.render_as_string(hide_password=False), original.set(database="test_dianzi_r07_input_audit_fix1_20261016").render_as_string(hide_password=False), original.password}
patterns = {encoded.encode() for value in values for encoded in (value, html.escape(value), quote(value, safe=""), json.dumps(value)[1:-1])}
changed = subprocess.check_output(["git", "diff", "--name-only", "014de585413c8a82a04d00b1ff2fbd1ff62d733b", "0c57b559fe2f0d93f8a5359383f1db6cc7abc6f5"], cwd=ROOT, text=True).splitlines()
paths = [*sorted(RUN.rglob("*")), *(ROOT / name for name in changed), ROOT / "reports/tasks/R07-input-audit-fix1.md"]
scanned = set()
matches = []
for path in paths:
    if not path.is_file() or "__pycache__" in path.parts or path.name == "actual_sensitive_value_scan.json" or path in scanned:
        continue
    scanned.add(path)
    raw = path.read_bytes()
    if any(pattern in raw for pattern in patterns):
        matches.append(path.relative_to(ROOT).as_posix())
receipt = {"started_at": started, "ended_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"), "files_scanned": len(scanned), "actual_test_resource_values_scanned": len(values), "matches": matches, "exit_code": int(bool(matches)), "values_and_their_hashes": "not recorded", "production_credentials_holdout_caches": "not read"}
(RUN / "actual_sensitive_value_scan.json").write_bytes(json.dumps(receipt, indent=2).encode())
print(json.dumps({"files_scanned": len(scanned), "matches": len(matches), "exit_code": receipt["exit_code"]}))
raise SystemExit(receipt["exit_code"])
