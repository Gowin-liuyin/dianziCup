"""真实浏览器只提交一条问题，不做付费重试，失败保留原始状态。"""

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

root = Path(__file__).resolve().parents[3]
run = Path(__file__).resolve().parent / "product_live_dc014c9"
assert not (run / "browser.json").exists()
public = json.loads((run.parent / "product_live_23c1878/question_start.json").read_text(encoding="utf-8"))
environment = dict(os.environ, DIANZI_LIVE_EVENT_ID=public["request"]["event_ids"][0], PLAYWRIGHT_BROWSERS_PATH="C:/Users/yinha/.codex/cache/dianzi/r01_playwright_1248")
redactions = json.loads(environment.pop("DIANZI_LOG_SECRET_VALUES"))
redactions += [environment.get("DIANZI_E2E_PASSWORD", "")]
values = sorted({value for value in redactions if value} | {value[index:index + 8] for value in redactions if value for index in range(max(0, len(value) - 7))}, key=len, reverse=True)
command = ["node", str(root / "frontend/node_modules/@playwright/test/cli.js"), "test", "--config", str(run.parent / "playwright_product_dc014.config.mjs")]
clock = ZoneInfo("Asia/Shanghai")
started = datetime.now(clock).isoformat(timespec="seconds")
result = subprocess.run(command, cwd=root / "frontend", env=environment, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=150)
output = result.stdout + result.stderr
for secret in values:
    output = output.replace(secret, "[REDACTED]")
(run / "browser.log").write_text(output, encoding="utf-8")
receipt = {"started_at": started, "ended_at": datetime.now(clock).isoformat(timespec="seconds"), "command": command, "cwd": str(root / "frontend"), "exit_code": result.returncode, "backend_and_frontend_code_sha": "dc014c960f19605c20e0d8e98a93e7c217f94cc6", "browser_test_state": "root new live test working file; source recorded separately", "maximum_questions": 1, "maximum_supplier_attempts": 2, "fee": "unknown", "fixture_routes": False, "login_path": "real HTTP login using browser-context request; earlier source runs cover form login"}
(run / "browser.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
print(json.dumps(receipt))
print(json.dumps(output[-2200:]))
raise SystemExit(result.returncode)
