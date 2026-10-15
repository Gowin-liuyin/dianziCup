"""冻结已审来源工作台的真实浏览器运行段，保留前段结束与中断。"""

import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

run = Path(__file__).resolve().parent
sha = "afe490ce15e567bf916d2e7b970354ddff3e193e"
root = Path("C:/Users/yinha/.codex/worktrees/r04-real-pipeline/dianzi")
assert (run / "live_segment_5_after_quota_reset/runtime_end.json").is_file()
assert (run / "frontend_live_8f6bd9_segment5/end.json").is_file()
assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip() == sha
for old, new in (
    ("supervise_windows_segment5.py", "supervise_windows_segment6.py"),
    ("launch_windows_segment5.ps1", "launch_windows_segment6.ps1"),
    ("serve_frontend_segment5.py", "serve_frontend_segment6.py"),
):
    path = run / new
    assert not path.exists()
    content = (run / old).read_text(encoding="utf-8")
    content = content.replace("8f6bd9f62b4bfb91c61ba47caaa7d6414fe6ecce", sha)
    content = content.replace("live_segment_5_after_quota_reset", "live_segment_6_source_workspace")
    content = content.replace("frontend_live_8f6bd9_segment5", "frontend_live_afe490_segment6")
    content = content.replace("supervise_windows_segment5.py", "supervise_windows_segment6.py")
    content = content.replace("windows_supervisor_8f6bd9_segment5", "windows_supervisor_afe490_segment6")
    path.write_text(content, encoding="utf-8")
config = run / "playwright_live.config.mjs"
content = config.read_text(encoding="utf-8").replace(
    "file:///C:/Users/yinha/.codex/worktrees/r04-real-pipeline/dianzi/frontend/node_modules/",
    "file:///D:/dianzi/frontend/node_modules/",
)
content = content.replace('testMatch: "r04_real_sources.spec.ts"', 'testMatch: ["r04_real_sources.spec.ts", "r17_real_source_workspace.spec.ts"]')
config.write_text(content, encoding="utf-8")
(run / "segment6_preparation.json").write_text(json.dumps({
    "prepared_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
    "code_sha": sha, "maximum_runtime_seconds": 900,
    "previous_segments_ended": True, "database_or_cursor_reset": False,
    "private_configuration": "reuses existing runtime_8f6bd9.json credentials and isolated DB; code SHA asserted separately",
}, indent=2), encoding="utf-8")
print("segment6 prepared; no process started by this helper")
