"""Require actual Neo4j shutdown logs and exit zero before allowing one restoration."""

import json
from datetime import datetime, timezone
from pathlib import Path

OUTPUT = Path(__file__).resolve().parent
stop = json.loads((OUTPUT / "graceful_stop.json").read_text())
assert stop["container_exit_code"] == stop["docker_exit_code"] == 0
assert (
    stop["old_owned_processes_absent"]
    and not stop["state"]["Running"]
    and stop["state"]["Pid"] == 0
)
assert not stop["state"]["OOMKilled"]
logs = (OUTPUT / "container_startup.redacted.log").read_text()
assert "INFO  Stopping..." in logs and "INFO  Stopped." in logs
assert "FATAL tini" not in logs and "Operation not permitted" not in logs
command = json.loads((OUTPUT / "stop_supervisor_signal_15.command.json").read_text())
duration = (
    datetime.fromisoformat(command["ended_at"])
    - datetime.fromisoformat(command["started_at"])
).total_seconds()
assert command["exit_code"] == 0 and 0 < duration < 15
stop.update(
    graceful_shutdown="passed",
    neo4j_shutdown_completed=True,
    tini_forwarding_error_present=False,
    docker_stop_seconds=duration,
    verified_at=datetime.now(timezone.utc).isoformat(),
)
(OUTPUT / "graceful_verified.json").write_text(json.dumps(stop, indent=2) + "\n")
print(
    json.dumps(
        {
            "container_id": stop["container_id"],
            "graceful_shutdown": "passed",
            "container_exit_code": 0,
            "docker_exit_code": 0,
            "neo4j_shutdown_completed": True,
            "docker_stop_seconds": duration,
            "deadline": stop["deadline"],
        }
    )
)
