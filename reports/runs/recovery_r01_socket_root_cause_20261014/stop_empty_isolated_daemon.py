"""Stop only this dedicated, empty daemon and preserve its first lifecycle receipt."""

import json
import os
import signal
import subprocess
import time
from pathlib import Path


cache = Path("/tmp/dianzi-docker-static-r01-20261014")
runtime = cache / "runtime"
assert cache.resolve() == cache and os.getuid() == 0
command = [str(cache / "portable/docker/docker"), "--config", str(runtime / "client-config"),
           "--host", "unix://" + str(runtime / "docker.sock"), "ps", "--all", "--quiet"]
result = subprocess.run(command, capture_output=True, check=True, timeout=5)
assert not result.stdout.strip(), "Do not interrupt any containers on this instance."
lifecycle = json.loads((runtime / "lifecycle.json").read_text())
supervisor_pid = lifecycle["supervisor_pid"]
assert lifecycle["ended_at"] is None
assert b"supervise_isolated_daemon.py" in Path(f"/proc/{supervisor_pid}/cmdline").read_bytes()
os.kill(supervisor_pid, signal.SIGTERM)
deadline = time.monotonic() + 18
while time.monotonic() < deadline:
    lifecycle = json.loads((runtime / "lifecycle.json").read_text())
    if lifecycle["ended_at"] is not None and not Path(f"/proc/{supervisor_pid}").exists():
        break
    time.sleep(0.2)
else:
    raise RuntimeError("Dedicated supervisor did not stop within 18 seconds.")
assert lifecycle["exit_code"] == 0
(cache / "first-daemon-lifecycle.json").write_text(json.dumps(lifecycle, indent=2))
(cache / "first-dockerd.log").write_bytes((runtime / "dockerd.log").read_bytes())
print(json.dumps(lifecycle, indent=2))
