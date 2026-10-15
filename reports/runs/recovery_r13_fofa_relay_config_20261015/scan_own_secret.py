"""仅比对被授权的新relay秘密，输出匹配计数，不输出秘密或匹配文本。"""

import json
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RUN_DIRECTORY = Path(__file__).parent
WORKTREE = RUN_DIRECTORY.parents[2]
OWN_PATHS = [
    WORKTREE / "backend/src/ai_intel/assets/fofa_relay.py",
    WORKTREE / "backend/tests/unit/test_r13_fofa_relay.py",
    WORKTREE / "backend/tests/contract/test_r13_fofa_relay_account_wire.py",
    WORKTREE / "backend/tests/security/test_r13_fofa_relay_boundaries.py",
    WORKTREE / "config/providers/fofa_relay.example.md",
    WORKTREE / "reports/tasks/R13-fofa-relay-config.md",
    *RUN_DIRECTORY.glob("*"),
]
secret = os.environ["DIANZI_FOFA_RELAY_API_KEY"]
scanned = 0
matched = 0
for path in OWN_PATHS:
    if not path.is_file():
        continue
    body = path.read_bytes()
    scanned += 1
    if any(value.encode() in body for value in {secret, secret.upper(), secret.lower()}):
        matched += 1
receipt = {
    "recorded_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
    "scanned_files": scanned,
    "new_relay_credential_matches": matched,
    "secret_sources_read": 1,
    "network_requests": 0,
    "scope": "owned adapter/tests/config/report/run artifacts only",
}
RUN_DIRECTORY.joinpath("secret_scan.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
print(json.dumps(receipt))
raise SystemExit(1 if matched else 0)
