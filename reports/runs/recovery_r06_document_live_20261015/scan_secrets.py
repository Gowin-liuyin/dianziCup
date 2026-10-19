"""Scan this run's text artifacts against authorized exact secret values."""

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RUN = Path(__file__).resolve().parent
private = subprocess.run(["wsl", "-d", "Ubuntu-22.04", "-u", "root", "--exec", "cat", "/tmp/dianzi-r04-live-20261015/private/runtime_8f6bd9.json"], capture_output=True, text=True, check=True, timeout=10)
configuration = json.loads(private.stdout)
secrets = {str(value) for value in configuration["secret_values"] if value}
secrets.add(os.environ["DIANZI_E2E_PASSWORD"])
paths = [path for path in RUN.rglob("*") if path.is_file() and path.suffix in {".py", ".ps1", ".json", ".jsonl", ".md", ".log"}]
report = RUN.parents[1] / "tasks/R06-document-live.md"
if report.is_file():
    paths.append(report)
matches = []
for path in paths:
    content = path.read_text(encoding="utf-8-sig")
    count = sum(secret in content for secret in secrets)
    if count:
        matches.append({"file": str(path), "exact_secret_values_found": count})
receipt = {"observed_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"), "files_scanned": len(paths), "matching_files": matches, "secrets_echoed": False, "result": "passed" if not matches else "failed", "scope": "Authorized runtime and DPAPI login values only; no other provider vault or holdout was read."}
(RUN / "secret_scan.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
print(json.dumps(receipt))
raise SystemExit(bool(matches))
