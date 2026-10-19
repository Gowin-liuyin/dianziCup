"""Check only the original daemon endpoint with a finite readiness deadline."""

import json
import subprocess
import time

from restore_services import DOCKER, OUTPUT, now

started_at = now()
deadline = time.monotonic() + 15
attempts = []
while time.monotonic() < deadline:
    attempt = subprocess.run(
        [*DOCKER, "version", "--format", "{{json .Server}}"],
        capture_output=True,
        text=True,
        timeout=3,
        check=False,
    )
    attempts.append({"at": now(), "exit_code": attempt.returncode})
    if attempt.returncode == 0:
        server = json.loads(attempt.stdout)
        assert server["Version"] == "29.2.0"
        receipt = {
            "started_at": started_at,
            "ended_at": now(),
            "attempts": attempts,
            "server_version": server["Version"],
            "api_version": server["ApiVersion"],
        }
        (OUTPUT / "daemon_readiness.json").write_text(json.dumps(receipt, indent=2))
        print(json.dumps(receipt))
        break
    time.sleep(1)
else:
    raise RuntimeError(
        "Owned daemon not ready within 15 seconds; private log retained."
    )
