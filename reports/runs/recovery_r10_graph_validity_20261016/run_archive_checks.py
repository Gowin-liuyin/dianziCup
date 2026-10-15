"""记录归档空白检查；不裁剪原始工具 stdout 或旧 red 日志。"""

import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
receipts = []
for label, arguments in [
    ("staged_code_diff", ["diff", "--cached", "--check", "--", "backend", "docs/decisions/CR-R10_graph_validity.md"]),
    ("staged_archive_diff", ["diff", "--cached", "--check"]),
]:
    assert not (RUN / (label + ".log")).exists()
    command = ["git", *arguments]
    started = datetime.now(timezone(timedelta(hours=8))).isoformat()
    result = subprocess.run(command, cwd=ROOT, capture_output=True)
    (RUN / (label + ".log")).write_bytes(result.stdout + result.stderr)
    receipts.append({"command": command, "cwd": str(ROOT), "started_at": started, "finished_at": datetime.now(timezone(timedelta(hours=8))).isoformat(), "exit_code": result.returncode, "code_commit": "3516b9109b9b7f2c5691d78ad0439aea4a659f4f"})
    print(json.dumps({"label": label, "exit_code": result.returncode}))
(RUN / "archive_diff_commands.json").write_text(json.dumps(receipts, ensure_ascii=False, indent=2), encoding="utf-8")
