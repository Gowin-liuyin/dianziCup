"""Install the approved graph dependencies into an isolated runtime and preserve lock evidence."""

import json
import os
import subprocess
import tomllib
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = ROOT / "reports/runs/recovery_r14_langgraph_dependencies_20261016"
RUN.mkdir(exist_ok=True)


def clock():
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


old = tomllib.loads(subprocess.check_output(["git", "show", "6878863202709dbe7b1ea77225c191bf1835be40:backend/uv.lock"], cwd=ROOT).decode())
current = tomllib.loads((ROOT / "backend/uv.lock").read_text(encoding="utf-8-sig"))
old_versions = {item["name"]: item["version"] for item in old["package"]}
new_versions = {item["name"]: item["version"] for item in current["package"]}
assert all(new_versions[name] == version for name, version in old_versions.items())
assert new_versions["langgraph"] == "1.2.15"
assert new_versions["langgraph-checkpoint-postgres"] == "3.2.0"
task_environment = os.environ.copy()
task_environment["UV_PROJECT_ENVIRONMENT"] = "D:/dianzi-runtime-cache/r14-langgraph-runtime-20261016/.venv"
command = ["C:/Users/yinha/.local/bin/uv.exe", "sync", "--project", str(ROOT / "backend"), "--frozen"]
started = clock()
with (RUN / "isolated_sync.stdout.log").open("xb") as stdout, (RUN / "isolated_sync.stderr.log").open("xb") as stderr:
    result = subprocess.run(command, env=task_environment, cwd=ROOT, stdout=stdout, stderr=stderr, timeout=120, check=False)
receipt = {"started_at": started, "ended_at": clock(), "command": command, "cwd": str(ROOT), "exit_code": result.returncode, "runtime": task_environment["UV_PROJECT_ENVIRONMENT"], "existing_packages_unchanged": True, "added_packages": {name: version for name, version in new_versions.items() if name not in old_versions}, "shared_backend_environment_modified": False, "model_download": False, "whole_r14_passed": False}
(RUN / "dependency_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps(receipt))
raise SystemExit(result.returncode)
