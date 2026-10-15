"""Search actual private credential values without printing, hashing or persisting them."""

import html
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
private = json.loads(subprocess.check_output(["wsl.exe", "-d", "Ubuntu-22.04", "-u", "root", "--exec", "cat", "/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json"], stderr=subprocess.PIPE))
values = {value for key, value in private.items() if isinstance(value, str) and len(value) >= 8 and any(marker in key.lower() for marker in ("password", "database_url", "redis_url", "token", "secret", "api_key"))}
values.update(value for key, value in os.environ.items() if len(value) >= 8 and any(marker in key.lower() for marker in ("password", "secret", "token", "api_key")))
patterns = {encoded.encode() for value in values for encoded in (value, quote(value, safe=""), html.escape(value), json.dumps(value)[1:-1])}
source_paths = subprocess.check_output(["git", "diff", "--name-only", "e61d9d6dd1215c337755d32d112dfe70f13d9e94"], cwd=ROOT, text=True).splitlines()
paths = [*sorted(RUN.rglob("*")), *(ROOT / name for name in source_paths), *ROOT.glob("backend/tests/**/*idempotency*.py"), ROOT / "docs/decisions/CR-R07_idempotency_scope_proposal.md", ROOT / "reports/tasks/R07-idempotency-scope.md"]
matches = []
scanned = set()
for path in paths:
    if not path.is_file() or path.name == "actual_value_scan.json" or path in scanned:
        continue
    scanned.add(path)
    content = path.read_bytes()
    if any(pattern in content for pattern in patterns):
        matches.append(path.relative_to(ROOT).as_posix())
receipt = {"started_at": started, "completed_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"), "files_scanned": len(scanned), "actual_sensitive_values_scanned": len(values), "matches": matches, "exit_code": 1 if matches else 0, "values_and_their_hashes": "not recorded", "scope": "owned code, tests, copied probes and run artifacts; external review probes retain the shared redaction hook"}
(RUN / "actual_value_scan.json").write_bytes(json.dumps(receipt, indent=2).encode())
print(json.dumps({"files_scanned": len(scanned), "matches": len(matches), "exit_code": receipt["exit_code"]}))
raise SystemExit(receipt["exit_code"])
