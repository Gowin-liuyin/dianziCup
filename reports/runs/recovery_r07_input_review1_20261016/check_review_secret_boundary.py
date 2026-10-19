"""Check review-owned artifacts against active connection secrets without printing them."""

import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
private = json.loads(subprocess.check_output(["wsl.exe", "-u", "root", "--exec", "cat", "/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json"], stderr=subprocess.PIPE))
secrets = [value.encode() for key, value in private.items() if isinstance(value, str) and value and ("password" in key.lower() or "url" in key.lower())]
paths = [path for path in RUN.rglob("*") if path.is_file() and "__pycache__" not in path.parts]
for path in paths:
    raw = path.read_bytes()
    assert all(secret not in raw for secret in secrets), "private connection content found in review artifact"
del private, secrets
result = {"recorded_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(), "checked_files": len(paths), "matched_private_connection_values": 0, "secrets_written": False, "credentials_source_copied": False}
(RUN / "review_secret_boundary.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result))
