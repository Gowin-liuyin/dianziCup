"""主控提交快照与已授权实际秘密精确比较；只输出路径与匹配数量。"""

import json
import os
import subprocess
from datetime import datetime
from zoneinfo import ZoneInfo

clock = ZoneInfo("Asia/Shanghai")
started_at = datetime.now(clock).isoformat(timespec="seconds")
secret_names = (
    "DIANZI_SCAN_DEEPSEEK_API_KEY",
    "DIANZI_SCAN_HUNTER_API_KEY",
    "DIANZI_SCAN_FOFA_API_KEY",
    "DIANZI_SCAN_QUAKE_API_KEY",
    "DIANZI_SCAN_ZOOMEYE_API_KEY",
    "DIANZI_SCAN_TEST_PASSWORD",
)
assert all(os.environ.get(name) for name in secret_names), "required secret references unavailable"
secret_bytes = tuple(os.environ[name].encode() for name in secret_names)
filenames = subprocess.check_output(["git", "diff", "--cached", "--name-only", "-z"]).split(b"\0")
matched_paths: list[str] = []
checked_paths: list[str] = []
for encoded_path in filenames:
    if not encoded_path:
        continue
    filename = encoded_path.decode("utf-8")
    captured = subprocess.run(["git", "show", ":" + filename], capture_output=True, check=True)
    checked_paths.append(filename)
    if any(secret in captured.stdout for secret in secret_bytes):
        matched_paths.append(filename)
receipt = {
    "started_at": started_at,
    "ended_at": datetime.now(clock).isoformat(timespec="seconds"),
    "source": "git staged blob; authorized secret environment; exact bytes",
    "checked_paths": checked_paths,
    "checked_secret_references": len(secret_names),
    "matches": len(matched_paths),
    "matched_paths": matched_paths,
}
print(json.dumps(receipt, ensure_ascii=False, indent=2))
raise SystemExit(1 if matched_paths else 0)
