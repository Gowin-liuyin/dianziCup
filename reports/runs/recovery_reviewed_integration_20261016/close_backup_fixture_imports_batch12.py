"""Restore the two frozen helper imports needed to collect the qualified PG tests."""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
MATERIAL = "ab04855085f828548222443c31020852f7ca2970"
started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
paths = ["reports/runs/recovery_r20_backup_restore_20261016/process_metadata.py", "reports/runs/recovery_r20_backup_restore_20261016/restart_read.py"]
records = []
pending = []
for relative in paths:
    target = ROOT / relative
    if target.exists():
        raise RuntimeError("existing unowned helper; refusing overwrite")
    raw = subprocess.check_output(["git", "show", MATERIAL + ":" + relative], cwd=ROOT)
    pending.append((target, raw))
    records.append({"path": relative, "material_sha": MATERIAL, "git_blob": subprocess.check_output(["git", "rev-parse", MATERIAL + ":" + relative], cwd=ROOT, text=True).strip(), "raw_sha256": hashlib.sha256(raw).hexdigest()})
for target, raw in pending:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(raw)
(RUN / "backup_batch12_helper_imports.json").write_text(json.dumps({"started_at": started, "ended_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"), "files": records, "scope": "Windows test helpers only; no database/model/resource mutation; old incomplete resource wrapper checks.py not adopted"}, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps({"helper_files": len(records)}))
