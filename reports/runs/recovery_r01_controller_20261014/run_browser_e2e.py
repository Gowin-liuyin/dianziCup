"""真实浏览器运行；凭据只继承环境，输出先脱敏再保存。"""

import json
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

run_directory = Path(__file__).resolve().parent
frontend = Path(os.environ["DIANZI_E2E_SOURCE_DIRECTORY"])
assert frontend.name == "frontend" and (frontend / "e2e/r01_auth.spec.ts").is_file()
clock = ZoneInfo("Asia/Shanghai")
started_at = datetime.now(clock).isoformat(timespec="seconds")
started_monotonic = time.monotonic()
report_path = run_directory / "browser_e2e_retry_4.xml"
environment = dict(os.environ)
environment["PLAYWRIGHT_JUNIT_OUTPUT_FILE"] = str(report_path)
command = [
    "node",
    "node_modules/@playwright/test/cli.js",
    "test",
    "--reporter=junit",
    "--output=" + str(run_directory / "browser_e2e_retry_4_artifacts"),
]
result = subprocess.run(command, cwd=frontend, env=environment, capture_output=True, timeout=120)
secret_bytes = tuple(
    os.environ[name].encode()
    for name in ("DIANZI_E2E_PASSWORD", "DATABASE_URL", "REDIS_URL")
    if os.environ.get(name)
)
redactions = 0


def redact_output(output: bytes) -> bytes:
    """包括框架失败call-log在内的输出，仅移除实际已注入秘密，不改变结果。"""
    global redactions
    for secret in secret_bytes:
        redactions += output.count(secret)
        output = output.replace(secret, b"[redacted integration credential]")
    return output


(run_directory / "browser_e2e_retry_4.stdout.log").write_bytes(redact_output(result.stdout))
(run_directory / "browser_e2e_retry_4.stderr.log").write_bytes(redact_output(result.stderr))
if report_path.exists():
    report_path.write_bytes(redact_output(report_path.read_bytes()))
receipt = {
    "started_at": started_at,
    "ended_at": datetime.now(clock).isoformat(timespec="seconds"),
    "elapsed_seconds": round(time.monotonic() - started_monotonic, 3),
    "command": command,
    "cwd": str(frontend),
    "frontend_code_sha": "9334fad3ee896a3bb0510c00e5940b9a897a015f",
    "backend_code_sha": "b504c2376142c6557ac3cfa7c42ffe2baa0dbca4",
    "exit_code": result.returncode,
    "redactions": redactions,
    "trace_video_failure_screenshot": "off",
    "credential_source": "DPAPI-injected controlled test account; no product model credentials",
}
(run_directory / "browser_e2e_retry_4.command.json").write_text(
    json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(json.dumps(receipt, ensure_ascii=False))
raise SystemExit(result.returncode)
