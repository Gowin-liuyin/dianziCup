"""保存单次实际检查命令、+08时钟、退出码及原始日志，不读取模型凭据。"""

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


def main() -> None:
    run_directory = Path(__file__).resolve().parent
    workspace = run_directory.parents[2]
    command_name, cwd, *command = sys.argv[1:]
    environment = os.environ.copy()
    environment["PYTHONUTF8"] = "1"
    environment["PYTHONIOENCODING"] = "utf-8"
    environment["PYTHONPATH"] = os.pathsep.join(
        [str(workspace / "backend" / "src"), str(workspace / "backend" / "tests")]
    )
    timezone_offset = timezone(timedelta(hours=8))
    started = datetime.now(timezone_offset)
    result = subprocess.run(
        command, cwd=cwd, env=environment, capture_output=True, encoding="utf-8", errors="replace"
    )
    finished = datetime.now(timezone_offset)
    (run_directory / f"{command_name}.log").write_text(
        result.stdout + result.stderr, encoding="utf-8"
    )
    receipt = {
        "command": command,
        "cwd": cwd,
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "exit_code": result.returncode,
        "log": f"{command_name}.log",
    }
    (run_directory / f"{command_name}.command.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(receipt, ensure_ascii=False))
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
