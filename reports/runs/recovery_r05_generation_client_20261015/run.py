"""独立覆盖率文件与真实时间收据；本工作包不读取产品凭据。"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent


def now():
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


name = sys.argv[1]
command = sys.argv[2:]
environment = dict(os.environ)
environment["PYTHONUTF8"] = "1"
sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
environment["PYTHONPATH"] = os.pathsep.join([str(ROOT/"backend/src"), str(ROOT/"backend/tests/unit")])
coverage_directory = Path.home()/".codex/tmp/dianzi-r05-generation-client-20261015/coverage"
coverage_directory.mkdir(parents=True,exist_ok=True)
environment["COVERAGE_FILE"] = str(coverage_directory/(".coverage_"+name))
started = now()
result = subprocess.run(command, cwd=ROOT/"backend", env=environment,
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                        encoding="utf-8", errors="replace")
ended = now()
(RUN/(name+".log")).write_text(result.stdout, encoding="utf-8")
receipt = {"started_at":started, "completed_at":ended, "timezone":"Asia/Shanghai",
           "cwd":str(ROOT/"backend"), "command":command, "exit_code":result.returncode,
           "code_sha":subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(),
           "actual_external_model_calls":0, "mode":"isolated tests; not live",
           "coverage_file":environment["COVERAGE_FILE"]}
(RUN/(name+".receipt.json")).write_text(json.dumps(receipt,indent=2),encoding="utf-8")
print(json.dumps(receipt))
print(result.stdout[-4500:])
raise SystemExit(result.returncode)
