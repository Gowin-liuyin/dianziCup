"""执行冻结依赖下的纯测试/静态检查，记录真实时间、退出码和输出哈希。"""

import hashlib
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RUN_DIRECTORY = Path(__file__).parent
WORKTREE = RUN_DIRECTORY.parents[2]
BACKEND = WORKTREE / "backend"
OWN_FILES = [
    "src/ai_intel/assets/fofa_relay.py",
    "tests/unit/test_r13_fofa_relay.py",
    "tests/contract/test_r13_fofa_relay_account_wire.py",
    "tests/security/test_r13_fofa_relay_boundaries.py",
]
COMMANDS = [
    ("unit", [sys.executable, "-m", "pytest", OWN_FILES[1], "--no-cov", "-q"]),
    ("contract", [sys.executable, "-m", "pytest", OWN_FILES[2], "--no-cov", "-q"]),
    ("security", [sys.executable, "-m", "pytest", OWN_FILES[3], "--no-cov", "-q"]),
    (
        "network_regressions",
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/unit/test_r03_network_gateway.py",
            "tests/unit/test_r03_network_review_regressions.py",
            "tests/unit/test_r03_doh_resolver.py",
            "tests/security/test_t08_network_and_sources.py",
            "tests/security/test_r03_network_transport.py",
            "tests/contract/test_t08_network_redirects.py",
            "--no-cov",
            "-q",
        ],
    ),
    ("ruff", [sys.executable, "-m", "ruff", "check", *OWN_FILES]),
    ("format", [sys.executable, "-m", "ruff", "format", "--check", *OWN_FILES]),
    ("mypy", [sys.executable, "-m", "mypy", OWN_FILES[0]]),
    ("default_unit_gate", [sys.executable, "-m", "pytest", "tests/unit", "-q"]),
]
receipts: list[dict[str, object]] = []
for name, command in COMMANDS:
    started_at = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
    completed = subprocess.run(command, cwd=BACKEND, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    log_path = RUN_DIRECTORY / f"{name}.log"
    log_path.write_bytes(completed.stdout)
    receipt = {
        "name": name,
        "cwd": str(BACKEND),
        "argv": command,
        "started_at": started_at,
        "finished_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
        "exit_code": completed.returncode,
        "log": log_path.name,
        "sha256": hashlib.sha256(completed.stdout).hexdigest(),
    }
    receipts.append(receipt)
    (RUN_DIRECTORY / "check_commands.json").write_text(
        json.dumps(receipts, ensure_ascii=True, indent=2), encoding="utf-8"
    )
    print(json.dumps(receipt), flush=True)
raise SystemExit(1 if any(receipt["exit_code"] != 0 for receipt in receipts) else 0)
