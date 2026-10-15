"""沿用私密身份和原库，单独封存修复版本的受控运行段。"""

import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

run = Path(__file__).resolve().parent
old_sha = "23c18784d71f1ed788072e6b3f2af70bac94fcb1"
sha = "dc014c960f19605c20e0d8e98a93e7c217f94cc6"
root = Path("C:/Users/yinha/.codex/worktrees/r04-real-pipeline/dianzi")
assert (run / "product_live_23c1878/runtime_end.json").is_file()
assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip() == sha
segment = run / "product_live_dc014c9"
segment.mkdir(exist_ok=False)
for old, new in (("supervise_product_live.py", "supervise_product_live_dc014.py"), ("launch_product_live.ps1", "launch_product_live_dc014.ps1")):
    content = (run / old).read_text(encoding="utf-8").replace(old_sha, sha).replace("23c1878", "dc014c9")
    if old.endswith(".ps1"):
        content = content.replace("supervise_product_live.py", "supervise_product_live_dc014.py").replace("prepare_product_live.py", "prepare_product_live_dc014.py")
    (run / new).write_text(content, encoding="utf-8")
frontend = (run.parent / "recovery_r04_source_jobs_20261015/serve_frontend_segment6.py").read_text(encoding="utf-8")
frontend = frontend.replace("afe490ce15e567bf916d2e7b970354ddff3e193e", sha).replace("frontend_live_afe490_segment6", "product_live_dc014c9/frontend").replace("30分钟", "15分钟")
(run / "serve_frontend_dc014.py").write_text(frontend, encoding="utf-8")
(segment / "preparation.json").write_text(json.dumps({"prepared_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"), "code_sha": sha, "prior_code_sha": old_sha, "previous_segment_ended": True, "migration": "already0014; verify before start, no downgrade/reset", "maximum_runtime_seconds": 900, "paid_browser_questions_maximum": 1, "supplier_calls_maximum": 2}, indent=2), encoding="utf-8")
print("repaired runtime helpers prepared; no process or model call started")
