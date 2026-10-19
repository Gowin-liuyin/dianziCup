"""保存默认推荐路由集成的实际运行时间、原始日志与退出码。"""

import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
ZONE = ZoneInfo("Asia/Shanghai")
python = str(ROOT / "backend/.venv/Scripts/python.exe")
tests = [
    "backend/tests/contract/test_r15_default_recommendation_mount.py",
    "backend/tests/unit/test_r15_http_recommendation_inputs.py",
    "backend/tests/unit/test_r15_persistent_subscription_rules.py",
    "backend/tests/contract/test_r15_http_recommendation_schema.py",
    "backend/tests/contract/test_r15_persistent_subscription_contracts.py",
    "backend/tests/security/test_r15_http_fix1_scope.py",
    "backend/tests/security/test_r15_http_recommendation_boundaries.py",
    "backend/tests/security/test_r02_default_auth_failure.py",
]
command = [python, "-m", "pytest", *tests, "-o", "addopts=", "--no-cov", "-q", "--junitxml=" + str(RUN / "r15_default_mount_fix2.xml")]
started = datetime.now(ZONE).isoformat(timespec="seconds")
result = subprocess.run(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
(RUN / "r15_default_mount_fix2.log").write_bytes(result.stdout)
receipt = {"started_at": started, "ended_at": datetime.now(ZONE).isoformat(timespec="seconds"), "cwd": str(ROOT), "command": command, "exit_code": result.returncode, "source_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(), "working_changes": ["backend/src/ai_intel/api/app.py", "backend/src/ai_intel/api/recommendation_contracts.py", "backend/tests/contract/test_r15_default_recommendation_mount.py"], "log": "r15_default_mount_fix2.log", "original_red_preserved": ["r15_default_mount.xml", "r15_default_mount_fix1.xml"], "fixture_correction": "valid frozen wire requests and session_expired problem code; no business assertions or original tests changed"}
(RUN / "r15_default_mount_fix2.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(receipt, ensure_ascii=True))
print(result.stdout.decode("utf-8", errors="replace")[-1500:])
raise SystemExit(result.returncode)
