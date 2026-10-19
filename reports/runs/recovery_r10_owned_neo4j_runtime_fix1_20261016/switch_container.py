"""Replace only the approved exited CID, preserving the same marked volume and deadline."""

import hashlib
import importlib.util
import json
import os
import signal
import socket
import time
from datetime import datetime
from pathlib import Path

import runtime

OLD_OUTPUT = runtime.OUTPUT.parent / "recovery_r10_owned_neo4j_runtime_20261016"
OLD_OWNED = Path("/tmp/dianzi-r10-neo4j-operations-20261016")
OLD_CID = "c0d49f69954c9d7b5d3ab0420347b99d96e9fdbeaf87ece3032b8c3430cd41ab"
SPECIFICATION = importlib.util.spec_from_file_location(
    "frozen_old_runtime", OLD_OUTPUT / "runtime.py"
)
assert SPECIFICATION is not None and SPECIFICATION.loader is not None
old_runtime = importlib.util.module_from_spec(SPECIFICATION)
SPECIFICATION.loader.exec_module(old_runtime)
assert (
    hashlib.sha256((OLD_OUTPUT / "runtime.py").read_bytes()).hexdigest()
    == "d78da438dd23fa50f0adc0f0f519dcccd5f95870d3c941ea47e20933f243dc3e"
)
assert runtime.now() < datetime.fromisoformat(runtime.DEADLINE)
assert runtime.OWNED.exists() and runtime.OWNED.resolve() == runtime.OWNED
assert runtime.OWNED.stat().st_mode & 0o777 == 0o700
assert json.loads((runtime.OUTPUT / "business_window_ack.json").read_text())[
    "no_write_window_ack"
]
manifest_bytes = (OLD_OUTPUT / "artifact_hashes.json").read_bytes()
assert (
    hashlib.sha256(manifest_bytes).hexdigest()
    == "614305594e9f5073511aaaed4396fc247045a350f5b9200e98d74979813342a6"
)
manifest = json.loads(manifest_bytes)
checked = []
for artifact in manifest["artifacts"]:
    path = Path(
        artifact["path"].replace("D:\\dianzi\\", "/mnt/d/dianzi/").replace("\\", "/")
    )
    assert (
        path.is_relative_to(OLD_OUTPUT)
        or path == runtime.OUTPUT.parents[1] / "tasks/R10-owned-neo4j-runtime.md"
    )
    content = path.read_bytes()
    assert (
        len(content) == artifact["byte_length"]
        and hashlib.sha256(content).hexdigest() == artifact["sha256"]
    )
    checked.append({"path": str(path), "sha256": artifact["sha256"]})
assert len(checked) == 143
runtime.write_json(
    runtime.OUTPUT / "original_seal_proof.json",
    {
        "at": runtime.now().isoformat(),
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "member_count": len(checked),
        "checked_members": checked,
    },
)
archive = runtime.OUTPUT / "original_live_lifecycle_before_switch"
archive.mkdir()
archived = []
for name in (
    "termination.json",
    "stop_supervisor_signal_15.command.json",
    "stop_supervisor_signal_15.stdout.log",
    "stop_supervisor_signal_15.stderr.log",
):
    source = OLD_OUTPUT / name
    content = source.read_bytes()
    (archive / name).write_bytes(content)
    archived.append(
        {
            "path": str(source),
            "sha256": hashlib.sha256(content).hexdigest(),
            "byte_length": len(content),
        }
    )
runtime.write_json(archive / "named_member_hashes.json", archived)
resource = json.loads((OLD_OWNED / "resource.json").read_text())
assert (
    resource["container_id"] == OLD_CID and resource["creator_token"] == runtime.CREATOR
)
assert resource["deadline"] == runtime.DEADLINE
container = runtime.inspect_container(OLD_CID)
old_runtime.assert_owned_container(container, resource)
assert container["state"]["Running"]
assert Path(resource["volume_mountpoint"]).stat().st_ino == 701675
assert (
    old_runtime.process_identity(resource["supervisor"]["pid"])
    == resource["supervisor"]
)
assert old_runtime.process_identity(resource["guardian"]["pid"]) == resource["guardian"]
runtime.write_json(
    runtime.OUTPUT / "old_container_before_switch.json",
    {
        "at": runtime.now().isoformat(),
        "resource": resource,
        "container": container,
        "stop_check": old_runtime.stop_owned("fix1_preflight", check=True),
    },
)
old_pids = [
    int(value)
    for value in (
        Path("/sys/fs/cgroup")
        / resource["container_process"]["cgroup"].split("::", 1)[1].lstrip("/")
        / "cgroup.procs"
    )
    .read_text()
    .split()
]
old_processes = [runtime.process_identity(pid) for pid in old_pids]
old_cgroup = Path("/sys/fs/cgroup") / resource["container_process"]["cgroup"].split(
    "::", 1
)[1].lstrip("/")
old_limits = {
    field: (old_cgroup / field).read_text().strip()
    for field in ("memory.max", "memory.swap.max", "cpu.max", "pids.max")
}
assert old_limits == {
    "memory.max": "1610612736",
    "memory.swap.max": "0",
    "cpu.max": "100000 100000",
    "pids.max": "128",
}
runtime.write_json(
    runtime.OUTPUT / "old_kernel_before_switch.json",
    {
        "at": runtime.now().isoformat(),
        "cgroup": str(old_cgroup),
        "limits": old_limits,
        "owned_pids": old_pids,
        "boot_id": resource["boot_id"],
    },
)
os.kill(resource["supervisor"]["pid"], signal.SIGTERM)
wait_until = time.monotonic() + 35
while True:
    assert time.monotonic() < wait_until, "Old owned generation failed bounded stop"
    container = runtime.inspect_container(OLD_CID)
    old_runtime.assert_owned_container(container, resource)
    alive = False
    for identity in [resource["supervisor"], resource["guardian"], *old_processes]:
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
runtime.write_json(
    runtime.OUTPUT / "old_container_stopped.json",
    {
        "at": runtime.now().isoformat(),
        "state": container["state"],
        "exact_old_cid": OLD_CID,
        "old_processes": old_processes,
        "old_owned_processes_absent": True,
        "bounded_stop": "passed",
        "graceful_shutdown": "failed_original_caps",
        "old_termination": json.loads((OLD_OWNED / "termination.json").read_text()),
    },
)
for name in (
    "termination.json",
    "stop_supervisor_signal_15.command.json",
    "stop_supervisor_signal_15.stdout.log",
    "stop_supervisor_signal_15.stderr.log",
):
    content = (OLD_OUTPUT / name).read_bytes()
    (archive / ("after_" + name)).write_bytes(content)
volume = json.loads(
    runtime.docker(
        [
            "volume",
            "inspect",
            "--format",
            '{"name":{{json .Name}},"mountpoint":{{json .Mountpoint}},"labels":{{json .Labels}}}',
            runtime.VOLUME,
        ]
    )
)
assert volume["mountpoint"] == resource["volume_mountpoint"]
assert (
    volume["labels"]["dianzi.creator_token"] == runtime.CREATOR
    and volume["labels"]["dianzi.owner"] == runtime.OWNER
)
assert volume["labels"]["dianzi.deadline"] == runtime.DEADLINE
assert Path(volume["mountpoint"]).stat().st_ino == 701675
runtime.docker(["rm", OLD_CID], label="remove_exact_exited_old_cid")
assert runtime.docker(["ps", "-aq", "--filter", "name=^/" + runtime.NAME + "$"]) == ""
for port in (27687, 27474):
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", port))
environment_path = runtime.OWNED / "neo4j-auth.env"
assert (
    environment_path.resolve() == environment_path
    and environment_path.stat().st_mode & 0o777 == 0o600
)
labels = {
    "dianzi.owner": runtime.OWNER,
    "dianzi.resource_id": runtime.NAME,
    "dianzi.creator_token": runtime.CREATOR,
    "dianzi.deadline": runtime.DEADLINE,
    "dianzi.runtime_generation": runtime.RUNTIME_GENERATION,
}
arguments = [
    "create",
    "--name",
    runtime.NAME,
    "--network",
    "host",
    "--restart",
    "no",
    "--memory",
    "1536m",
    "--memory-swap",
    "1536m",
    "--cpus",
    "1",
    "--pids-limit",
    "128",
    "--security-opt",
    "no-new-privileges:true",
    "--cap-drop",
    "ALL",
    "--log-driver",
    "json-file",
    "--log-opt",
    "max-size=10m",
    "--log-opt",
    "max-file=1",
    "--mount",
    "type=volume,source=" + runtime.VOLUME + ",target=/data",
    "--env-file",
    str(environment_path),
]
arguments.extend(
    piece
    for capability in sorted(runtime.CAPABILITIES)
    for piece in ("--cap-add", capability)
)
arguments.extend(
    piece for pair in labels.items() for piece in ("--label", "=".join(pair))
)
arguments.extend(
    piece for pair in runtime.CONFIG.items() for piece in ("--env", "=".join(pair))
)
try:
    container_id = runtime.docker(
        [*arguments, runtime.IMAGE], label="create_fix1_container"
    )
finally:
    assert (
        environment_path.resolve() == environment_path
        and environment_path.parent == runtime.OWNED
    )
    environment_path.unlink()
container = runtime.inspect_container(container_id)
new_resource = {
    "resource_id": runtime.NAME,
    "deadline": runtime.DEADLINE,
    "creator_token": runtime.CREATOR,
    "boot_id": resource["boot_id"],
    "container_id": container_id,
    "container_created_at": container["created"],
    "volume_mountpoint": volume["mountpoint"],
    "volume_inode": 701675,
    "runtime_generation": runtime.RUNTIME_GENERATION,
    "prior_container_id": OLD_CID,
    "switch_prepared_at": runtime.now().isoformat(),
    "input_git_sha": "5b29b3e8c6ea1d10ca50cf2d2006f8460b53253c",
    "superseded_runtime_sha256": "d78da438dd23fa50f0adc0f0f519dcccd5f95870d3c941ea47e20933f243dc3e",
}
runtime.assert_owned_container(container, new_resource)
assert {
    value.removeprefix("CAP_") for value in container["cap_add"]
} == runtime.CAPABILITIES
runtime.write_json(runtime.OWNED / "resource.json", new_resource)
runtime.write_json(runtime.OUTPUT / "resource_created.json", new_resource)
print(
    json.dumps(
        {
            "new_container_id": container_id,
            "prior_container_id": OLD_CID,
            "deadline": runtime.DEADLINE,
            "volume_inode": 701675,
            "runtime_generation": runtime.RUNTIME_GENERATION,
            "started": False,
        }
    )
)
