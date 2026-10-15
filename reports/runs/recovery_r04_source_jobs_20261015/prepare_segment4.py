"""停止收据确认后准备固定新版本运行；不重置PG事实或旧来源流。"""

import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
WORKTREE = Path("C:/Users/yinha/.codex/worktrees/r04-real-pipeline/dianzi")
SHA = "8f6bd9f62b4bfb91c61ba47caaa7d6414fe6ecce"
OLD_SHA = "7184dc63525ae3e8ea439ec64fc03dfaa629f7a8"
started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
assert (RUN / "live_segment_3_vendor_fixed/runtime_end.json").exists()
assert (RUN / "frontend_live_7184/end.json").exists()
assert subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"], cwd=WORKTREE) == b""
subprocess.run(["git", "checkout", "--detach", SHA], cwd=WORKTREE, check=True, capture_output=True)

private_code = """import json,pathlib,os
old=pathlib.Path('/tmp/dianzi-r04-live-20261015/private/runtime_7184.json')
target=old.with_name('runtime_8f6bd9.json')
assert not target.exists()
value=json.loads(old.read_text())
value['code_sha']='8f6bd9f62b4bfb91c61ba47caaa7d6414fe6ecce'
target.write_text(json.dumps(value));os.chmod(target,0o600)
"""
subprocess.run(["wsl", "-d", "Ubuntu-22.04", "-u", "root", "--exec", "python3", "-c", private_code], check=True, capture_output=True)
replacements = {
    OLD_SHA: SHA, "live_segment_3_vendor_fixed": "live_segment_4_link_cursor",
    "runtime_7184.json": "runtime_8f6bd9.json", "7184-20261015-beat": "8f6bd9-20261015-beat",
    "windows_supervisor_7184": "windows_supervisor_8f6bd9", "supervise_windows.py": "supervise_windows_segment4.py",
    "frontend_live_7184": "frontend_live_8f6bd9", "1800": "900",
}
for source, target in [
    ("supervise_windows.py", "supervise_windows_segment4.py"),
    ("launch_windows.ps1", "launch_windows_segment4.ps1"),
    ("serve_frontend.py", "serve_frontend_segment4.py"),
    ("collect_live.py", "collect_live_segment4.py"),
]:
    target_path = RUN / target
    assert not target_path.exists()
    content = (RUN / source).read_text(encoding="utf-8")
    for old, new in replacements.items():
        content = content.replace(old, new)
    if source == "collect_live.py":
        content = content.replace('"max_pages": 20, "stream_kind": "backfill"', '"max_pages": 5, "stream_kind": "live"')
        content = content.replace('FROM source_cursors ORDER BY source_id', "FROM source_cursors WHERE stream_kind='live' ORDER BY source_id")
    target_path.write_text(content, encoding="utf-8")
(RUN / "segment4_preparation.json").write_text(json.dumps({"started_at": started,
    "ended_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
    "code_sha": SHA, "previous_code_sha": OLD_SHA,
    "old_processes_stopped_receipts_present": True, "database_reset": False,
    "new_collection_stream": "live", "max_pages_per_source": 5,
    "maximum_runtime_seconds": 900, "private_configuration_in_repository": False}, indent=2))
print("segment4 fixed worktree and bounded helpers prepared")
