"""Replay original retained public bytes without replacing historical observations."""

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
ZONE = ZoneInfo("Asia/Shanghai")
source = (RUN / "replay_catalogues.py").read_text(encoding="utf-8")
target = RUN / "replay_catalogues_fix2.py"
target.write_text(source.replace('"catalogue_replay_observation.json"', '"catalogue_replay_fix2_observation.json"'), encoding="utf-8")
command = [sys.executable, str(target)]
started = datetime.now(ZONE).isoformat()
result = subprocess.run(command, cwd=ROOT / "backend", capture_output=True, text=True)
(RUN / "catalogue_replay_fix2.log").write_text(result.stdout + result.stderr, encoding="utf-8")
record = {"code_sha": "7aeb85ae8277c048fb762dbc705436602cb18f9d", "command": command,
          "cwd": str(ROOT / "backend"), "started_at": started,
          "completed_at": datetime.now(ZONE).isoformat(), "exit_code": result.returncode,
          "network_requests": 0, "model_calls": 0, "official_schema": "failed"}
(RUN / "catalogue_replay_fix2_command.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
print(json.dumps(record))
print(result.stdout)
raise SystemExit(result.returncode)
