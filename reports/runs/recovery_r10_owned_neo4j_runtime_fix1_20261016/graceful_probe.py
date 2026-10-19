"""Stop only the current owned generation and require exit zero and complete process removal."""

import json
import os
import shutil
import signal
import time
from pathlib import Path

import runtime

resource = json.loads((runtime.OWNED / "resource.json").read_text())
container = runtime.inspect_container(resource["container_id"])
runtime.assert_owned_container(container, resource)
assert (
    resource["creator_token"] == runtime.CREATOR
    and resource["deadline"] == runtime.DEADLINE
)
assert container["state"]["Running"]
assert {
    value.removeprefix("CAP_") for value in container["cap_add"]
} == runtime.CAPABILITIES
assert runtime.process_identity(resource["supervisor"]["pid"]) == resource["supervisor"]
assert runtime.process_identity(resource["guardian"]["pid"]) == resource["guardian"]
assert (
    json.loads((runtime.OUTPUT / "sentinel_create.json").read_text())["container_id"]
    == resource["container_id"]
)
cgroup = Path("/sys/fs/cgroup") / resource["container_process"]["cgroup"].split(
    "::", 1
)[1].lstrip("/")
identities = [
    runtime.process_identity(int(pid))
    for pid in (cgroup / "cgroup.procs").read_text().split()
]
archive = runtime.OUTPUT / "before_graceful_probe"
archive.mkdir()
for name in (
    "resource_started.json",
    "resource_created.json",
    "kernel_security.json",
    "bolt_smoke.json",
    "windows_health.json",
    "launch_initial.json",
    "container_start.command.json",
    "container_start.stdout.log",
    "container_start.stderr.log",
):
    shutil.copy2(runtime.OUTPUT / name, archive / name)
requested_at = runtime.now()
os.kill(resource["supervisor"]["pid"], signal.SIGTERM)
wait_until = time.monotonic() + 35
while True:
    assert time.monotonic() < wait_until, (
        "Graceful stop exceeded the original bounded shutdown budget"
    )
    container = runtime.inspect_container(resource["container_id"])
    runtime.assert_owned_container(container, resource)
    alive = False
    for identity in [resource["supervisor"], resource["guardian"], *identities]:
        try:
            current = runtime.process_identity(identity["pid"])
        except (FileNotFoundError, ProcessLookupError):
            continue
        if (
            current["boot_id"] == identity["boot_id"]
            and current["start_ticks"] == identity["start_ticks"]
        ):
            alive = True
    if (
        not alive
        and not container["state"]["Running"]
        and container["state"]["Pid"] == 0
    ):
        break
    time.sleep(1)
termination = json.loads((runtime.OWNED / "termination.json").read_text())
receipt = {
    "requested_at": requested_at.isoformat(),
    "observed_stopped_at": runtime.now().isoformat(),
    "container_id": resource["container_id"],
    "state": container["state"],
    "container_exit_code": container["state"]["ExitCode"],
    "docker_exit_code": termination["docker_exit_code"],
    "old_owned_processes_absent": True,
    "old_process_identities": identities,
    "bounded_stop": "passed",
    "graceful_shutdown": "exit_zero_pending_shutdown_log",
    "termination": termination,
    "deadline": resource["deadline"],
}
runtime.write_json(runtime.OUTPUT / "graceful_stop.json", receipt)
assert container["state"]["ExitCode"] == 0 and not container["state"]["OOMKilled"]
print(json.dumps(receipt))
