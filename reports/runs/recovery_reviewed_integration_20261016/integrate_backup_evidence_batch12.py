"""Integrate only the qualified backup slice and hash-verified plan evidence inputs."""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
SOURCE = "12f9e8cd2f1e7073427c2959fdbc799b90fc44fe"
REVIEW = "ab04855085f828548222443c31020852f7ca2970"
BACKUP_PATHS = [
    "scripts/backup_restore.py",
    "backend/tests/unit/test_r20_backup_restore.py",
    "backend/tests/integration/test_r20_backup_restore_pg.py",
    "docs/runbooks/recovery_backup_restore.md",
]


def timestamp():
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


started = timestamp()
baseline = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
if baseline != "1c3c33808053227b8502443ebdff4c848c66e62b":
    raise RuntimeError("baseline changed")
if subprocess.check_output(["git", "diff", "--cached", "--name-only"], cwd=ROOT).strip():
    raise RuntimeError("staged files already exist")
evidence = json.loads((RUN / "plan_evidence_input_closure_batch8.json").read_text(encoding="utf-8"))
if evidence["closure_count"] != 22 or len(evidence["files"]) != 22:
    raise RuntimeError("evidence roster changed")
for item in evidence["files"]:
    raw = (ROOT / item["path"]).read_bytes()
    if len(raw) != item["bytes"] or hashlib.sha256(raw).hexdigest() != item["raw_sha256"]:
        raise RuntimeError("evidence changed; refusing to overwrite or adopt " + item["path"])
sources = []
for relative in BACKUP_PATHS:
    target = ROOT / relative
    if target.exists():
        raise RuntimeError("existing file needs ownership review: " + relative)
    raw = subprocess.check_output(["git", "show", SOURCE + ":" + relative], cwd=ROOT)
    qualified = subprocess.check_output(["git", "show", REVIEW + ":" + relative], cwd=ROOT)
    if raw != qualified:
        raise RuntimeError("qualified source differs: " + relative)
    sources.append((target, raw))
for target, raw in sources:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(raw)
receipt = {
    "started_at": started, "ended_at": timestamp(), "baseline_sha": baseline,
    "source_sha": SOURCE, "independent_review_sha": REVIEW,
    "files": [{"path": path.relative_to(ROOT).as_posix(), "raw_sha256": hashlib.sha256(raw).hexdigest()} for path, raw in sources],
    "plan_evidence_inputs": [{"path": item["path"], "raw_sha256": item["raw_sha256"]} for item in evidence["files"]],
    "source_limits": "backup PG/local objects slice qualified; actual MinIO and index rebuild still not_run; no Root PG run in this integration",
    "stage_accepted": False, "push": "not_run",
}
(RUN / "backup_evidence_batch12_inputs.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps({"source_files": 4, "verified_evidence_inputs": 22, "stage_accepted": False}))
