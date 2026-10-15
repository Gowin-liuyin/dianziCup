"""只在固定前端版本运行真实API浏览器，输出在写盘前移除测试秘密。"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

FRONTEND = Path.home() / ".codex/worktrees/recovery-r04-frontend-review/dianzi/frontend"
RUN = Path("D:/dianzi/reports/runs/recovery_r04_frontend_review_1_20261015")
PROFILES = {"real": ("0b983349e0468a4c75a1adf9f050ac3e7dd00686", "real-api-auth", "real-api-auth-artifacts")}



def now() -> str:
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def main() -> int:
    """限定loopback测试账号和五例交互，失败仍保留实际结果。"""
    profile = sys.argv[1] if len(sys.argv) > 1 else "real"
    expected_sha, label, artifact_directory = PROFILES[profile]
    frontend = FRONTEND
    run = RUN
    if profile == "review":
        frontend = Path.home() / ".codex/worktrees/recovery-hacker-ui-review/dianzi/frontend"
        run = Path(__file__).resolve().parents[3] / "reports/runs/recovery_hacker_ui_review_1_20261015"
    code_sha = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=frontend, text=True
    ).strip()
    if code_sha != expected_sha:
        raise RuntimeError("frontend no longer matches the frozen browser input")
    run.mkdir(exist_ok=True, parents=True)
    output_path = run / f"{label}.json"
    if output_path.exists():
        raise FileExistsError("browser evidence label already used")
    environment = dict(os.environ)
    environment.update(
        API_PROXY_TARGET="http://127.0.0.1:28000",
        DIANZI_E2E_FRONTEND_URL="http://127.0.0.1:25305",
        PLAYWRIGHT_BROWSERS_PATH=str(Path.home() / ".codex/cache/dianzi/r01_playwright_1248"),
    )
    password = environment["DIANZI_E2E_PASSWORD"]
    command = ["node", "node_modules/@playwright/test/cli.js", "test", "--reporter=json",
               f"--output={run / artifact_directory}",
               "r01_auth.spec.ts"]
    started = now()
    completed = subprocess.run(command, cwd=frontend, env=environment,
                               capture_output=True, timeout=240)
    fragments = {password.encode()}
    if len(password) >= 8:
        fragments.update(password[index:index + 8].encode() for index in range(len(password) - 7))

    def redact(content: bytes) -> bytes:
        for value in sorted(fragments, key=len, reverse=True):
            content = content.replace(value, b"[redacted test credential]")
        return content

    output_path.write_bytes(redact(completed.stdout))
    (run / f"{label}.stderr.log").write_bytes(redact(completed.stderr))
    generated_artifacts = run / artifact_directory
    matches: list[str] = []
    if generated_artifacts.exists():
        for artifact in generated_artifacts.rglob("*"):
            if artifact.is_file() and any(value in artifact.read_bytes() for value in fragments):
                matches.append(str(artifact.relative_to(run)))
    receipt = {"started_at": started, "ended_at": now(), "command": command,
               "cwd": str(frontend), "exit_code": completed.returncode,
               "frontend_sha": code_sha, "backend_sha": "0b983349e0468a4c75a1adf9f050ac3e7dd00686",
               "backend_segment": "r04_auth_0b983", "artifact_secret_matches": matches,
               "trace_video_automatic_screenshot": "off"}
    (run / f"{label}.command.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps(receipt))
    if matches:
        raise RuntimeError("browser artifact contains test credential; quarantine before integration")
    try:
        print(json.loads(completed.stdout).get("stats", {}))
    except (json.JSONDecodeError, UnicodeDecodeError):
        print("browser output is not structured JSON; inspect redacted evidence")
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
