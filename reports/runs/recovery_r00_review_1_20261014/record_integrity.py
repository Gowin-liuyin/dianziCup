"""Record immutable hashes, indexed scope and initial review state."""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path
from run_commands import REVIEW, OUTPUT


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


history = (REVIEW / "progress/history/task_state_pre_recovery_8e265dc.json.txt").read_bytes()
original = subprocess.check_output(["git", "show", "8e265dc039a67319140f003f6a070ea714bf7bef:progress/task_state.json"], cwd=REVIEW)
indexed = {str(path.relative_to(REVIEW)).replace("\\", "/"): digest(path.read_bytes())
           for directory in ("scripts", "backend/src")
           for path in (REVIEW / directory).rglob("*.py")}
state = json.loads((REVIEW / "progress/task_state.json").read_text(encoding="utf-8"))
status_counts = {value: sum(entry["status"] == value for entry in state["tasks"].values())
                 for value in ("pending", "needs_changes", "accepted")}
record = {"recorded_at": datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds"),
          "candidate": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REVIEW).decode().strip(),
          "tree": subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], cwd=REVIEW).decode().strip(),
          "status": subprocess.check_output(["git", "status", "--short"], cwd=REVIEW).decode(),
          "core_autocrlf": subprocess.check_output(["git", "config", "--get", "core.autocrlf"], cwd=REVIEW).decode().strip(),
          "original_history_hash": digest(original), "archive_hash": digest(history), "archive_byte_identical_original": original == history,
          "indexed_scope": ["scripts/*.py", "backend/src/**/*.py"], "indexed_files": indexed,
          "current_task_counts": status_counts,
          "all_original_entries_eight_layers": all(len(entry["verification"]) == 8 for entry in state["tasks"].values()),
          "all_slices_current_pending": all(child["status"] == "pending" for entry in state["tasks"].values() for child in entry["slice_acceptance"].values())}
(OUTPUT / "integrity_snapshot.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({key: value for key, value in record.items() if key != "indexed_files"}, ensure_ascii=False, indent=2))
