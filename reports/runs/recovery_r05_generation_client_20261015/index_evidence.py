"""索引捕获字节与Git blob；仅静态检查新增证据，不读取产品或用户秘密文件。"""

import hashlib
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
paths = [path for path in RUN.rglob("*") if path.is_file() and not path.name.startswith(".coverage")
         and path.name not in {"evidence_index.json", "static_secret_scan.json"}]
paths += [ROOT/"reports/tasks/R05-generation-client.md"]
paths += [ROOT/name for name in (
    "backend/src/ai_intel/infrastructure/models/clients.py",
    "backend/src/ai_intel/infrastructure/models/generation.py",
    "backend/src/ai_intel/infrastructure/models/json_output.py",
    "backend/tests/unit/test_r05_generation.py",
    "backend/tests/contract/test_r05_generation_wire.py",
    "backend/tests/integration/test_r05_generation_http.py",
)]
entries = []
matches = []
for path in paths:
    payload = path.read_bytes()
    if re.search(rb"sk-[a-zA-Z0-9]{20,}", payload):
        matches.append(str(path.relative_to(ROOT)))
    relative = path.relative_to(ROOT).as_posix()
    indexed = subprocess.run(["git", "show", ":"+relative], cwd=ROOT, stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL)
    entries.append({"path":relative, "captured_sha256":hashlib.sha256(payload).hexdigest(),
                    "captured_size_bytes":len(payload),
                    "git_blob_sha256":hashlib.sha256(indexed.stdout).hexdigest()
                    if indexed.returncode == 0 else None,
                    "git_blob_size_bytes":len(indexed.stdout) if indexed.returncode == 0 else None})
receipt = {"checked_at":datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
           "scope":"static long sk-token pattern only; synthetic fixture keys explicit; no actual keys read",
           "files_checked":len(entries), "matches":matches, "actual_model_calls":0}
(RUN/"evidence_index.json").write_text(json.dumps(entries,indent=2),encoding="utf-8")
(RUN/"static_secret_scan.json").write_text(json.dumps(receipt,indent=2),encoding="utf-8")
print(json.dumps(receipt))
raise SystemExit(1 if matches else 0)
