"""封存自有交付文件及实际字节哈希，不修改公共进度或业务版本。"""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RUN_DIRECTORY = Path(__file__).parent
WORKTREE = RUN_DIRECTORY.parents[2]
code_sha = subprocess.check_output(
    ["git", "rev-parse", "HEAD"], cwd=WORKTREE, text=True
).strip()
paths = [
    WORKTREE / "backend/src/ai_intel/assets/fofa_relay.py",
    WORKTREE / "backend/tests/unit/test_r13_fofa_relay.py",
    WORKTREE / "backend/tests/contract/test_r13_fofa_relay_account_wire.py",
    WORKTREE / "backend/tests/security/test_r13_fofa_relay_boundaries.py",
    WORKTREE / "config/providers/fofa_relay.example.md",
    WORKTREE / "reports/tasks/R13-fofa-relay-config.md",
    *RUN_DIRECTORY.glob("*"),
]
artifacts = []
for path in sorted(paths):
    if not path.is_file() or path.name == "artifact_manifest.json":
        continue
    body = path.read_bytes()
    artifacts.append(
        {
            "path": path.relative_to(WORKTREE).as_posix(),
            "bytes": len(body),
            "sha256": hashlib.sha256(body).hexdigest(),
        }
    )
manifest = {
    "recorded_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
    "task": "R13-fofa-relay-config",
    "status": "awaiting_review",
    "base_sha": "1a52e17ffe327fb8a0c1d4f97372948a699910e3",
    "code_sha": code_sha,
    "artifacts": artifacts,
}
RUN_DIRECTORY.joinpath("artifact_manifest.json").write_text(
    json.dumps(manifest, ensure_ascii=True, indent=2), encoding="utf-8"
)
print(json.dumps({"code_sha": code_sha, "artifact_files": len(artifacts)}))
