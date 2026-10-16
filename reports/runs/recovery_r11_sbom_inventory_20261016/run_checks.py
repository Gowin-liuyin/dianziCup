"""记录本切片命令原输出、退出码与真实上海起止；不打印连接配置。"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
PYTHON = ROOT / "backend/.venv/Scripts/python.exe"


def run(
    name: str,
    arguments: list[str],
    *,
    cwd: Path | None = None,
    environment: dict[str, str] | None = None,
) -> int:
    start = datetime.now(ZoneInfo("Asia/Shanghai"))
    result = subprocess.run(
        arguments,
        cwd=cwd or ROOT / "backend",
        env={**(environment or os.environ), "PYTHONIOENCODING": "utf-8"},
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    end = datetime.now(ZoneInfo("Asia/Shanghai"))
    output = result.stdout
    if environment and environment.get("TEST_DATABASE_URL"):
        from sqlalchemy.engine import make_url

        url = environment["TEST_DATABASE_URL"]
        output = output.replace(url.encode(), b"[redacted test connection]")
        password = make_url(url).password
        if password:
            output = output.replace(password.encode(), b"[redacted test credential]")
    (RUN / f"{name}.log").write_bytes(output)
    receipt = {
        "name": name,
        "argv": arguments,
        "cwd": str(cwd or ROOT / "backend"),
        "start": start.isoformat(timespec="seconds"),
        "end": end.isoformat(timespec="seconds"),
        "exit_code": result.returncode,
        "log": f"{name}.log",
    }
    with (RUN / "commands.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(receipt, ensure_ascii=False) + "\n")
    print(json.dumps(receipt, ensure_ascii=False))
    print(output.decode("utf-8", errors="replace")[-1500:])
    return result.returncode


if __name__ == "__main__":
    name, *arguments = sys.argv[1:]
    raise SystemExit(run(name, [str(PYTHON), *arguments]))
