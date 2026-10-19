"""Run only the new isolated diagnostic tests and preserve earlier receipts."""

import json
import os
import subprocess

from replay_originals import RUN, current_time

BACKEND = RUN.parents[2] / "backend"
commands = [
    ("synthetic_compatibility_red", [str(BACKEND / ".venv/Scripts/python.exe"), "-m", "pytest", "--no-cov", "-q",
        str(RUN / "test_minimal_release_regressions.py"), str(RUN / "test_minimal_avid_regressions.py"),
        "--junitxml=" + str(RUN / "synthetic_compatibility_red.xml")]),
    ("failure_retention_observation", [str(BACKEND / ".venv/Scripts/python.exe"), "-m", "pytest", "--no-cov", "-q",
        str(RUN / "test_failure_retention_observation.py"),
        "--junitxml=" + str(RUN / "failure_retention_observation.xml")]),
]
receipts = []
for label, argv in commands:
    started_at = current_time()
    result = subprocess.run(argv, cwd=BACKEND, env=dict(os.environ, PYTHONUTF8="1"),
                            capture_output=True, encoding="utf-8", timeout=90)
    (RUN / (label + ".log")).write_text(result.stdout + result.stderr, encoding="utf-8")
    receipts.append({"label": label, "argv": argv, "cwd": str(BACKEND), "started_at": started_at,
                     "finished_at": current_time(), "exit_code": result.returncode,
                     "environment_override": {"PYTHONUTF8": "1"}})
    print(result.stdout.splitlines()[-1])
(RUN / "final_check_commands.json").write_text(json.dumps(receipts, indent=2), encoding="utf-8")
