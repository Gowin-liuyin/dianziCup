"""匿名配额重置后重试有限公开采集；保留此前403和所有事实/游标。"""

import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RUN = Path(__file__).resolve().parent
CLOCK = ZoneInfo("Asia/Shanghai")
started = datetime.now(CLOCK)
assert started > datetime.fromisoformat("2026-10-15T15:07:53+08:00")
assert (RUN / "live_segment_4_link_cursor/runtime_end.json").exists()
assert (RUN / "frontend_live_8f6bd9/end.json").exists()
worktree = Path("C:/Users/yinha/.codex/worktrees/r04-real-pipeline/dianzi")
assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=worktree, text=True).strip() == "8f6bd9f62b4bfb91c61ba47caaa7d6414fe6ecce"
assert (worktree / "frontend/node_modules/vite/bin/vite.js").is_file()
for source, target in (
    ("supervise_windows_segment4.py", "supervise_windows_segment5.py"),
    ("launch_windows_segment4.ps1", "launch_windows_segment5.ps1"),
    ("serve_frontend_segment4.py", "serve_frontend_segment5.py"),
    ("collect_live_segment4.py", "collect_live_segment5.py"),
):
    target_path = RUN / target
    assert not target_path.exists()
    content = (RUN / source).read_text(encoding="utf-8")
    content = content.replace("live_segment_4_link_cursor", "live_segment_5_after_quota_reset")
    content = content.replace("frontend_live_8f6bd9", "frontend_live_8f6bd9_segment5")
    content = content.replace("supervise_windows_segment4.py", "supervise_windows_segment5.py")
    content = content.replace("windows_supervisor_8f6bd9", "windows_supervisor_8f6bd9_segment5")
    target_path.write_text(content, encoding="utf-8")
(RUN / "segment5_preparation.json").write_text(json.dumps({"started_at": started.isoformat(timespec="seconds"),
    "ended_at": datetime.now(CLOCK).isoformat(timespec="seconds"),
    "code_sha": "8f6bd9f62b4bfb91c61ba47caaa7d6414fe6ecce",
    "quota_reset_evidence": "github_limit_probe.json", "previous_403_preserved": True,
    "old_database_or_cursor_reset": False, "max_pages_each_source": 5,
    "maximum_runtime_seconds": 900, "frontend_previous_start_failed": "MODULE_NOT_FOUND vite; owned npm ci restored dependencies"}, indent=2))
print("bounded segment5 prepared after observed quota reset")
