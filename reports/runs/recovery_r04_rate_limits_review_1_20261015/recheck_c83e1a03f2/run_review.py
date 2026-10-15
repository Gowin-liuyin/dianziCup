"""独立评审命令收据；专用测试连接串只传入子进程环境。"""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
import subprocess
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

RUN = Path(__file__).resolve().parent
WT = Path("C:/Users/yinha/.codex/worktrees/r04-rate-recheck-1/dianzi")
BACKEND = WT / "backend"
PYTHON = BACKEND / ".venv/Scripts/python.exe"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    parser.add_argument("--pg", action="store_true")
    parser.add_argument("args", nargs=argparse.REMAINDER)
    parsed = parser.parse_args()
    arguments = parsed.args
    if arguments and arguments[0] == "--":
        arguments = arguments[1:]
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment["PYTHONUTF8"] = "1"
    secret_values: list[str] = []
    if parsed.pg:
        connection = subprocess.run(
            ["wsl", "-u", "root", "--", "cat",
             "/tmp/dianzi-docker-static-r01-20261014/runtime/r05-pgvector/connection.json"],
            capture_output=True, text=True, check=True,
        )
        configuration = json.loads(connection.stdout)
        environment["TEST_DATABASE_URL"] = configuration["TEST_DATABASE_URL"]
        environment["DIANZI_TEST_RUN_ID"] = "r05_pgvector_20261015"
        from urllib.parse import unquote, urlsplit
        secret_values = [configuration["TEST_DATABASE_URL"],
                         unquote(urlsplit(configuration["TEST_DATABASE_URL"]).password or "")]
    command = [str(PYTHON), *arguments]
    started_at = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
    process = subprocess.run(command, cwd=BACKEND, env=environment,
                             capture_output=True, text=True, encoding="utf-8", errors="replace")
    ended_at = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
    output = process.stdout + process.stderr
    for value in sorted(secret_values, key=len, reverse=True):
        if value:
            output = output.replace(value, "[redacted isolated test credential]")
    output = re.sub(r"postgres(?:ql)?(?:\+[a-z0-9_]+)?://[^\s)<>'\"]+",
                    "[redacted isolated test connection]", output)
    for artifact in RUN.glob("*.xml"):
        content = artifact.read_text(encoding="utf-8")
        for value in sorted(secret_values, key=len, reverse=True):
            if value:
                content = content.replace(value, "[redacted isolated test credential]")
        content = re.sub(r"postgres(?:ql)?(?:\+[a-z0-9_]+)?://[^\s)<>'\"]+",
                         "[redacted isolated test connection]", content)
        artifact.write_text(content, encoding="utf-8")
    log = RUN / f"{parsed.name}.log"
    log.write_text(output, encoding="utf-8")
    revision = subprocess.run(["git", "rev-parse", "HEAD", "HEAD^{tree}"], cwd=WT,
                              capture_output=True, text=True, check=True).stdout.splitlines()
    receipt = {"command": command, "cwd": str(BACKEND), "started_at": started_at,
               "ended_at": ended_at, "exit_code": process.returncode,
               "code_sha": revision[0], "code_tree": revision[1], "log": str(log),
               "isolated_pg": parsed.pg}
    (RUN / f"{parsed.name}.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2),
                                           encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=False))
    print("\n".join(output.splitlines()[-8:]))
    return process.returncode


if __name__ == "__main__":
    sys.exit(main())
