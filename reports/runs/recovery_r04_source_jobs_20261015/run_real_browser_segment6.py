"""记录冻结真实工作台的浏览器退出码与完整耗时，不记录登录输入。"""

import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

root = Path("D:/dianzi")
run = Path(__file__).resolve().parent
receipt = run / "real_browser_segment6.json"
assert not receipt.exists()
clock = ZoneInfo("Asia/Shanghai")
started = datetime.now(clock).isoformat(timespec="seconds")
command = ["node", str(root / "frontend/node_modules/@playwright/test/cli.js"), "test", "--config", str(run / "playwright_live.config.mjs")]
result = subprocess.run(command, cwd=root / "frontend", capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=240)
(run / "real_browser_segment6.log").write_text(result.stdout + result.stderr, encoding="utf-8")
record = {"started_at": started, "ended_at": datetime.now(clock).isoformat(timespec="seconds"),
          "code_sha": "afe490ce15e567bf916d2e7b970354ddff3e193e", "command": command,
          "cwd": str(root / "frontend"), "exit_code": result.returncode,
          "data_mode": "live; actual public source records and fixed-source worker; no route mocks",
          "paid_model_calls": 0, "fee": "unknown"}
receipt.write_text(json.dumps(record, indent=2), encoding="utf-8")
print(json.dumps(record))
print(json.dumps((result.stdout + result.stderr)[-4000:]))
raise SystemExit(result.returncode)
