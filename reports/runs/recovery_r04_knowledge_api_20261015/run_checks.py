"""仅本工作包的隔离测试入口；连接串只从WSL私密资源文件进入子进程环境。"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"


def now():
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def main():
    name = sys.argv[1]
    command = sys.argv[2:]
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(BACKEND / "src")
    if name == "integration_first":
        original = json.loads(Path("/tmp/dianzi-r04_sources_20261015/connection.json").read_text())
        original_url = make_url(original["TEST_DATABASE_URL"])
        target = "test_dianzi_r04_api_20261015"
        admin = create_engine(original_url, isolation_level="AUTOCOMMIT")
        with admin.connect() as connection:
            if not connection.scalar(text("SELECT 1 FROM pg_database WHERE datname=:name"), {"name": target}):
                connection.execute(text('CREATE DATABASE "test_dianzi_r04_api_20261015"'))
        admin.dispose()
        private = Path("/tmp/dianzi-r04-api-20261015")
        private.mkdir(mode=0o700, exist_ok=True)
        (private / "connection.json").write_text(json.dumps({
            "DIANZI_TEST_RUN_ID": "r04_api_20261015",
            "TEST_DATABASE_URL": original_url.set(database=target).render_as_string(hide_password=False),
        }))
        (private / "connection.json").chmod(0o600)
    if name.startswith("integration"):
        environment.update(json.loads(Path("/tmp/dianzi-r04-api-20261015/connection.json").read_text()))
    started = now()
    result = subprocess.run(command, cwd=BACKEND, env=environment, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    ended = now()
    (RUN / (name+".log")).write_text(result.stdout)
    windows_root = subprocess.check_output(["wslpath", "-w", str(ROOT)], text=True).strip()
    code_sha = subprocess.check_output(["/mnt/c/Program Files/Git/cmd/git.exe", "-C", windows_root,
                                        "rev-parse", "HEAD"], text=True).strip()
    receipt = {"started_at": started, "ended_at": ended, "timezone": "Asia/Shanghai",
               "cwd": str(BACKEND), "command": command, "exit_code": result.returncode,
               "code_sha": code_sha,
               "source_tree": "working tree, not frozen", "test_mode": "isolated fixture / actual PG"}
    (RUN / (name+".receipt.json")).write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt))
    print(result.stdout[-5000:])
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
