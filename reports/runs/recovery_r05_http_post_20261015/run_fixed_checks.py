"""固定命令的真实日志和退出码；不加载或输出任何产品秘密。"""

import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent / "fixed"
RUN.mkdir(exist_ok=False)
COMMANDS = {
    "network_regression": ["uv", "run", "--locked", "pytest", "tests/unit", "tests/contract/test_t08_network_redirects.py", "tests/security/test_t08_network_and_sources.py", "tests/security/test_r03_network_transport.py", "tests/security/test_r05_http_post.py", "--cov-report=json:" + str(RUN / "coverage.json"), "--junitxml=" + str(RUN / "tests.xml")],
    "ruff": ["uv", "run", "--locked", "ruff", "check", "src", "tests"],
    "format": ["uv", "run", "--locked", "ruff", "format", "--check", "src", "tests"],
    "mypy": ["uv", "run", "--locked", "mypy", "src"],
}

for name, command in COMMANDS.items():
    start = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
    with (RUN / (name + ".log")).open("wb") as log:
        result = subprocess.run(command, cwd=ROOT / "backend", stdout=log, stderr=subprocess.STDOUT)
    receipt = {"command": command, "cwd": str(ROOT / "backend"), "start": start,
               "end": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"), "exit_code": result.returncode,
               "scope": "root mutable candidate; source SHA to be frozen after tests, recorded fixtures not live"}
    (RUN / (name + ".receipt.json")).write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(name, result.returncode, flush=True)
