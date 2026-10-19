"""Record the review-only CRLF diff warning without rewriting its output."""

import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()
command = ["git", "diff", "HEAD^", "HEAD", "--check"]
result = subprocess.run(command, cwd=ROOT, capture_output=True)
(RUN / "review_raw_metadata_crlf_diff_check.log").write_bytes(result.stdout + result.stderr)
receipt = {"started_at": started, "completed_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(), "command": command, "cwd": str(ROOT), "exit_code": result.returncode, "review_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(), "cause": "New own fingerprint/seal JSON was written with Windows CRLF after -text byte preservation; CR treated as trailing whitespace.", "preceding_actual_cached_check_exit": 1, "preceding_commit_exit": 0, "orchestration_note": "Reviewer tool sequence did not gate the commit on cached-check status; this is retained as a reviewer instrument defect, not business success."}
(RUN / "review_raw_metadata_crlf_diff_check.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
print(json.dumps(receipt))
