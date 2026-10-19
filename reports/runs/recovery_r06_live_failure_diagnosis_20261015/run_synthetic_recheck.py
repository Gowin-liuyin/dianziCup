"""Preserve initial synthetic red log and recheck the corrected exception contract."""

import json
import os
import subprocess

from replay_originals import RUN, current_time

BACKEND = RUN.parents[2] / "backend"
command = [str(BACKEND / ".venv/Scripts/python.exe"), "-m", "pytest", "--no-cov", "-q",
           str(RUN / "test_minimal_release_regressions.py"),
           "--junitxml=" + str(RUN / "synthetic_release_red_recheck2.xml")]
started_at = current_time()
result = subprocess.run(command, cwd=BACKEND, env=dict(os.environ, PYTHONUTF8="1"),
                        capture_output=True, encoding="utf-8", timeout=90)
(RUN / "synthetic_release_red_recheck2.log").write_text(result.stdout + result.stderr, encoding="utf-8")
receipt = {"argv": command, "cwd": str(BACKEND), "started_at": started_at,
           "finished_at": current_time(), "exit_code": result.returncode,
           "environment_override": {"PYTHONUTF8": "1"},
           "prior_assertion_mistake": "adapter contract raises RepositoryFetchError, not ValueError; six negative cases had wrong expected exception type",
           "changed_product_code": False}
(RUN / "synthetic_release_red_recheck2_command.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
print(json.dumps(receipt, indent=2))
print(result.stdout.splitlines()[-1])
