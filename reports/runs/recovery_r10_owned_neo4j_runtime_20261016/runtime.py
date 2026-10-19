"""Operate only the explicitly authorised R10 Neo4j test resource."""

import argparse
import hashlib
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

OWNED = Path("/tmp/dianzi-r10-neo4j-operations-20261016")
OUTPUT = Path(__file__).resolve().parent
DOCKER_ROOT = Path("/tmp/dianzi-docker-static-r01-20261014")
DOCKER = [
    str(DOCKER_ROOT / "portable/docker/docker"),
    "--config",
    str(DOCKER_ROOT / "runtime/client-config"),
    "--host",
    "unix://" + str(DOCKER_ROOT / "runtime/docker.sock"),
]
NAME = "dianzi-r10-neo4j-test-20261016"
VOLUME = NAME + "-data"
IMAGE = "docker.io/library/neo4j@sha256:57ecb62bbb0c41c98fb69e08ee014c959926f3bd16ee8ef466c4a1e298f6157c"
IMAGE_ID = "sha256:57ecb62bbb0c41c98fb69e08ee014c959926f3bd16ee8ef466c4a1e298f6157c"
OWNER = "/root/r10_owned_neo4j_runtime_integration"
BOOT_FILE = Path("/proc/sys/kernel/random/boot_id")
CONFIG = {
    "NEO4J_server_default__listen__address": "127.0.0.1",
    "NEO4J_server_default__advertised__address": "127.0.0.1",
    "NEO4J_server_bolt_listen__address": "127.0.0.1:27687",
    "NEO4J_server_bolt_advertised__address": "127.0.0.1:27687",
    "NEO4J_server_http_listen__address": "127.0.0.1:27474",
    "NEO4J_server_http_advertised__address": "127.0.0.1:27474",
    "NEO4J_server_https_enabled": "false",
    "NEO4J_dbms_routing_enabled": "false",
    "NEO4J_server_memory_heap_initial__size": "512M",
    "NEO4J_server_memory_heap_max__size": "512M",
    "NEO4J_server_memory_pagecache_size": "512M",
    "NEO4J_db_transaction_timeout": "3s",
    "NEO4J_db_lock_acquisition_timeout": "2s",
}
CONTAINER_FORMAT = '{"id":{{json .Id}},"name":{{json .Name}},"created":{{json .Created}},"image_id":{{json .Image}},"configured_image":{{json .Config.Image}},"labels":{{json .Config.Labels}},"state":{{json .State}},"mounts":{{json .Mounts}},"memory":{{json .HostConfig.Memory}},"memory_swap":{{json .HostConfig.MemorySwap}},"nano_cpus":{{json .HostConfig.NanoCpus}},"pids_limit":{{json .HostConfig.PidsLimit}},"network":{{json .HostConfig.NetworkMode}},"cap_add":{{json .HostConfig.CapAdd}},"cap_drop":{{json .HostConfig.CapDrop}},"security_opt":{{json .HostConfig.SecurityOpt}},"restart_policy":{{json .HostConfig.RestartPolicy}},"log_config":{{json .HostConfig.LogConfig}}}'


def now():
    return datetime.now(timezone(timedelta(hours=8)))


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + ".writing")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    os.chmod(temporary, 0o600)
    temporary.replace(path)


def docker(arguments, timeout=25, label=None):
    started = now()
    result = subprocess.run(
        DOCKER + arguments, capture_output=True, text=True, timeout=timeout, check=False
    )
    if label:
        (OUTPUT / (label + ".stdout.log")).write_text(result.stdout)
        (OUTPUT / (label + ".stderr.log")).write_text(result.stderr)
        write_json(
            OUTPUT / (label + ".command.json"),
            {
                "argv": DOCKER + arguments,
                "started_at": started.isoformat(),
                "ended_at": now().isoformat(),
                "timeout_seconds": timeout,
                "exit_code": result.returncode,
            },
        )
    if result.returncode:
        raise RuntimeError(
            "Docker operation failed: "
            + " ".join(arguments[:2])
            + "; exit="
            + str(result.returncode)
        )
    return result.stdout.strip()


def process_identity(pid):
    process = Path("/proc") / str(pid)
    return {
        "pid": pid,
        "boot_id": BOOT_FILE.read_text().strip(),
        "start_ticks": process.joinpath("stat")
        .read_text()
        .split(")", 1)[1]
        .split()[19],
        "cmdline": process.joinpath("cmdline").read_bytes().decode().split("\0"),
        "cgroup": process.joinpath("cgroup").read_text().strip(),
    }


def inspect_container(container_id):
    return json.loads(
        docker(["container", "inspect", "--format", CONTAINER_FORMAT, container_id])
    )


def assert_owned_container(container, resource):
    assert resource["boot_id"] == BOOT_FILE.read_text().strip(), "Boot identity changed"
    assert container["id"] == resource["container_id"] and len(container["id"]) == 64
    assert container["name"] == "/" + NAME
    assert container["image_id"] == IMAGE_ID and container["configured_image"] == IMAGE
    assert container["created"] == resource["container_created_at"]
    labels = container["labels"]
    assert labels["dianzi.owner"] == OWNER
    assert labels["dianzi.resource_id"] == NAME
    assert labels["dianzi.creator_token"] == resource["creator_token"]
    assert labels["dianzi.deadline"] == resource["deadline"]
    data_mounts = [
        item for item in container["mounts"] if item["Destination"] == "/data"
    ]
    assert len(data_mounts) == 1 and data_mounts[0]["Type"] == "volume"
    assert (
        data_mounts[0]["Name"] == VOLUME
        and data_mounts[0]["Source"] == resource["volume_mountpoint"]
    )
    assert container["network"] == "host"
    if container["state"]["Running"]:
        observed = process_identity(container["state"]["Pid"])
        if resource.get("container_process"):
            assert (
                observed["start_ticks"] == resource["container_process"]["start_ticks"]
            )
        assert "/dianzi-r01-20261014/" in observed["cgroup"]


def stop_owned(reason, check=False):
    resource = json.loads((OWNED / "resource.json").read_text())
    container = inspect_container(resource["container_id"])
    assert_owned_container(container, resource)
    result = {
        "at": now().isoformat(),
        "reason": reason,
        "container_id": resource["container_id"],
        "identity_matched": True,
        "check_only": check,
        "running_before": container["state"]["Running"],
    }
    if not check and container["state"]["Running"]:
        docker(
            ["stop", "--time", "15", resource["container_id"]],
            timeout=25,
            label="stop_" + reason,
        )
        stopped = inspect_container(resource["container_id"])
        assert_owned_container(stopped, resource)
        assert not stopped["state"]["Running"]
        result["state_after"] = stopped["state"]
    if not check:
        write_json(OWNED / "termination.json", result)
        write_json(OUTPUT / "termination.json", result)
    return result


def preflight():
    assert os.getuid() == 0
    assert not OWNED.exists(), "Unknown owned path already exists"
    assert docker(["ps", "-aq", "--filter", "name=^/" + NAME + "$"]) == "", (
        "Container name already exists"
    )
    names = docker(["volume", "ls", "--format", "{{.Name}}"])
    assert VOLUME not in names.splitlines(), "Volume name already exists"
    for port in (27687, 27474):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", port))
    daemon = json.loads(
        docker(
            [
                "info",
                "--format",
                '{"version":{{json .ServerVersion}},"data_root":{{json .DockerRootDir}},"live_restore":{{json .LiveRestoreEnabled}}}',
            ]
        )
    )
    space = os.statvfs(daemon["data_root"])
    free_bytes = space.f_bavail * space.f_frsize
    assert free_bytes >= 4 * 1024**3, "Insufficient 4 GiB addition budget"
    result = {
        "at": now().isoformat(),
        "boot_id": BOOT_FILE.read_text().strip(),
        "daemon": daemon,
        "free_bytes": free_bytes,
        "disk_addition_budget_bytes": 4 * 1024**3,
        "compressed_layer_bytes": 351667694,
        "compressed_pull_limit_bytes": 1024**3,
        "container_name_absent": True,
        "volume_absent": True,
        "loopback_ports_available": [27687, 27474],
        "owned_path_absent": True,
    }
    write_json(OUTPUT / "preflight.json", result)
    return result


def pull():
    assert json.loads((OUTPUT / "preflight.json").read_text())["container_name_absent"]
    docker(
        ["pull", "--platform", "linux/amd64", IMAGE], timeout=600, label="image_pull_1"
    )
    return verify_image()


def verify_image():
    image = json.loads(
        docker(
            [
                "image",
                "inspect",
                "--platform",
                "linux/amd64",
                "--format",
                '{"id":{{json .Id}},"repo_digests":{{json .RepoDigests}},"size":{{json .Size}},"architecture":{{json .Architecture}},"os":{{json .Os}}}',
                IMAGE,
            ],
            label="image_inspect_verified",
        )
    )
    assert (
        image["id"] == IMAGE_ID
        and image["architecture"] == "amd64"
        and image["os"] == "linux"
    )
    assert image["size"] < 4 * 1024**3
    space = os.statvfs(DOCKER_ROOT / "runtime/data")
    free_bytes = space.f_bavail * space.f_frsize
    before = json.loads((OUTPUT / "preflight.json").read_text())["free_bytes"]
    assert before - free_bytes <= 4 * 1024**3
    assert free_bytes >= 4 * 1024**3
    image["filesystem_free_bytes"] = free_bytes
    image["observed_filesystem_consumption_delta_bytes"] = before - free_bytes
    image["filesystem_delta_scope"] = (
        "Whole daemon filesystem delta; concurrent service IO may contribute."
    )
    image["observed_at"] = now().isoformat()
    write_json(OUTPUT / "image_verified.json", image)
    return image


def prepare_rebuild():
    resource = json.loads((OWNED / "resource.json").read_text())
    assert (
        resource["container_id"]
        == "74a8b3d5916429588d9d93660381395e18638de3864f69574553b70aa7ad7689"
    )
    container = inspect_container(resource["container_id"])
    assert_owned_container(container, resource)
    assert not container["state"]["Running"]
    assert Path(resource["volume_mountpoint"]).stat().st_ino == resource["volume_inode"]
    volume_labels = json.loads(
        docker(["volume", "inspect", "--format", "{{json .Labels}}", VOLUME])
    )
    assert (
        volume_labels["dianzi.owner"] == OWNER
        and volume_labels["dianzi.creator_token"] == resource["creator_token"]
    )
    assert (
        volume_labels["dianzi.resource_id"] == NAME
        and volume_labels["dianzi.deadline"] == resource["deadline"]
    )
    for field in ("supervisor", "guardian"):
        try:
            observed = process_identity(resource[field]["pid"])
        except (FileNotFoundError, ProcessLookupError):
            continue
        assert observed != resource[field], "Prior owned process is still running"
    archive = OUTPUT / "initial_attempt"
    archive.mkdir()
    for file_name in (
        "container_create.command.json",
        "container_create.stdout.log",
        "container_create.stderr.log",
        "container_start.command.json",
        "container_start.stdout.log",
        "container_start.stderr.log",
        "resource_created.json",
        "resource_started.json",
        "termination.json",
        "launch.json",
        "logs_and_secret_scan.json",
        "container_startup.redacted.log",
    ):
        shutil.copy2(OUTPUT / file_name, archive / file_name)
    docker(
        ["rm", resource["container_id"]],
        label="remove_verified_exited_initial_container",
    )
    resource["prior_container_id"] = resource.pop("container_id")
    resource.pop("container_created_at")
    resource.pop("container_process")
    resource.pop("guardian")
    resource["rebuild_prepared_at"] = now().isoformat()
    write_json(OWNED / "resource.json", resource)
    termination = OWNED / "termination.json"
    assert termination.resolve() == termination and termination.parent == OWNED
    termination.rename(OWNED / "termination_initial.json")
    write_json(OUTPUT / "rebuild_preparation.json", resource)
    return {
        "operation": "verified_owned_exited_container_removed",
        "prior_container_id": resource["prior_container_id"],
        "volume_inode": resource["volume_inode"],
        "deadline_preserved": resource["deadline"],
    }


def supervisor(existing_volume=False):
    resource = json.loads((OWNED / "resource.json").read_text())
    assert resource["resource_id"] == NAME
    deadline = datetime.fromisoformat(resource["deadline"])
    assert 0 < (deadline - now()).total_seconds() <= 12 * 3600
    assert deadline <= datetime.fromisoformat("2026-10-17T21:49:15+08:00")
    assert docker(["ps", "-aq", "--filter", "name=^/" + NAME + "$"]) == ""
    if not existing_volume:
        assert (
            VOLUME not in docker(["volume", "ls", "--format", "{{.Name}}"]).splitlines()
        )
    else:
        assert (
            resource["prior_container_id"]
            == "74a8b3d5916429588d9d93660381395e18638de3864f69574553b70aa7ad7689"
        )
        assert (
            Path(resource["volume_mountpoint"]).stat().st_ino
            == resource["volume_inode"]
        )
    for port in (27687, 27474):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", port))
    resource.update(
        boot_id=BOOT_FILE.read_text().strip(), supervisor=process_identity(os.getpid())
    )
    labels = {
        "dianzi.owner": OWNER,
        "dianzi.resource_id": NAME,
        "dianzi.creator_token": resource["creator_token"],
        "dianzi.deadline": resource["deadline"],
    }
    label_arguments = [
        piece for pair in labels.items() for piece in ("--label", "=".join(pair))
    ]
    if not existing_volume:
        docker(["volume", "create", *label_arguments, VOLUME], label="volume_create")
    volume = json.loads(
        docker(
            [
                "volume",
                "inspect",
                "--format",
                '{"name":{{json .Name}},"mountpoint":{{json .Mountpoint}},"labels":{{json .Labels}}}',
                VOLUME,
            ]
        )
    )
    assert volume["labels"] == labels
    mountpoint = Path(volume["mountpoint"])
    expected_parent = DOCKER_ROOT / "runtime/data/volumes" / VOLUME
    assert (
        mountpoint == expected_parent / "_data" and mountpoint.resolve() == mountpoint
    )
    resource["volume_mountpoint"] = str(mountpoint)
    resource["volume_inode"] = mountpoint.stat().st_ino
    environment_path = OWNED / "neo4j-auth.env"
    assert (
        environment_path.resolve() == environment_path
        and (environment_path.stat().st_mode & 0o777) == 0o600
    )
    arguments = [
        "create",
        "--name",
        NAME,
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
        "--cap-add",
        "CHOWN",
        "--cap-add",
        "SETUID",
        "--cap-add",
        "SETGID",
        "--cap-add",
        "DAC_OVERRIDE",
        "--cap-add",
        "FOWNER",
        "--log-driver",
        "json-file",
        "--log-opt",
        "max-size=10m",
        "--log-opt",
        "max-file=1",
        *label_arguments,
        "--mount",
        "type=volume,source=" + VOLUME + ",target=/data",
        "--env-file",
        str(environment_path),
    ]
    arguments.extend(
        piece for pair in CONFIG.items() for piece in ("--env", "=".join(pair))
    )
    try:
        resource["container_id"] = docker([*arguments, IMAGE], label="container_create")
    finally:
        assert (
            environment_path.resolve() == environment_path
            and environment_path.parent == OWNED
        )
        environment_path.unlink()
    container = inspect_container(resource["container_id"])
    resource["container_created_at"] = container["created"]
    assert_owned_container(container, resource)
    write_json(OWNED / "resource.json", resource)
    write_json(OUTPUT / "resource_created.json", resource)
    run_supervision(resource)


def resume_stopped():
    resource = json.loads((OWNED / "resource.json").read_text())
    assert (
        resource["container_id"]
        == "c0d49f69954c9d7b5d3ab0420347b99d96e9fdbeaf87ece3032b8c3430cd41ab"
    )
    container = inspect_container(resource["container_id"])
    assert_owned_container(container, resource)
    assert not container["state"]["Running"] and container["state"]["ExitCode"] == 143
    termination = json.loads((OWNED / "termination.json").read_text())
    assert termination["reason"] == "guardian_heartbeat_stale"
    assert termination["container_id"] == resource["container_id"]
    assert Path(resource["volume_mountpoint"]).stat().st_ino == resource["volume_inode"]
    assert now() < datetime.fromisoformat(resource["deadline"])
    for field in ("supervisor", "guardian"):
        try:
            observed = process_identity(resource[field]["pid"])
        except (FileNotFoundError, ProcessLookupError):
            continue
        assert observed != resource[field], "Previous owned process is active"
    archive = OUTPUT / "stale_heartbeat_attempt"
    archive.mkdir()
    for name in (
        "container_create.command.json",
        "container_create.stdout.log",
        "container_create.stderr.log",
        "container_start.command.json",
        "container_start.stdout.log",
        "container_start.stderr.log",
        "resource_created.json",
        "termination.json",
        "launch_rebuild.json",
    ):
        shutil.copy2(OUTPUT / name, archive / name)
    for name in ("heartbeat.json", "termination.json"):
        source = OWNED / name
        assert source.resolve() == source and source.parent == OWNED
        original_bytes = source.read_bytes()
        (archive / ("owned_" + name)).write_bytes(original_bytes)
        write_json(
            archive / (name + ".sha256.json"),
            {
                "path": str(source),
                "sha256": hashlib.sha256(original_bytes).hexdigest(),
                "byte_length": len(original_bytes),
                "archived_at": now().isoformat(),
            },
        )
        source.rename(OWNED / (name + ".stale_attempt"))
    resource["supervisor"] = process_identity(os.getpid())
    resource.pop("guardian")
    resource.pop("started_at", None)
    resource.pop("supervisor_script_sha256", None)
    resource["resume_prepared_at"] = now().isoformat()
    write_json(OWNED / "resource.json", resource)
    write_json(OUTPUT / "resource_resume_prepared.json", resource)
    run_supervision(resource)


def run_supervision(resource):
    deadline = datetime.fromisoformat(resource["deadline"])
    guard = subprocess.Popen(
        [sys.executable, "-B", str(Path(__file__).resolve()), "guardian"],
        stdin=subprocess.DEVNULL,
        stdout=(OWNED / "guardian.stdout.log").open("w"),
        stderr=(OWNED / "guardian.stderr.log").open("w"),
        start_new_session=True,
    )
    resource["guardian"] = process_identity(guard.pid)
    write_json(OWNED / "resource.json", resource)
    write_json(OUTPUT / "resource_created.json", resource)
    reason = "supervisor_failure"
    requested = []
    signal.signal(
        signal.SIGTERM,
        lambda number, frame: requested.append("supervisor_signal_" + str(number)),
    )
    signal.signal(
        signal.SIGINT,
        lambda number, frame: requested.append("supervisor_signal_" + str(number)),
    )
    try:
        docker(["start", resource["container_id"]], label="container_start")
        container = inspect_container(resource["container_id"])
        assert_owned_container(container, resource)
        resource.update(
            started_at=now().isoformat(),
            container_process=process_identity(container["state"]["Pid"]),
            supervisor_script_sha256=hashlib.sha256(
                Path(__file__).read_bytes()
            ).hexdigest(),
        )
        write_json(OWNED / "resource.json", resource)
        write_json(OUTPUT / "resource_started.json", resource)
        monotonic_deadline = time.monotonic() + (deadline - now()).total_seconds()
        while True:
            if requested:
                reason = requested[0]
                break
            if now() >= deadline or time.monotonic() >= monotonic_deadline:
                reason = "deadline"
                break
            container = inspect_container(resource["container_id"])
            assert_owned_container(container, resource)
            if not container["state"]["Running"]:
                reason = "container_exited"
                break
            if guard.poll() is not None:
                reason = "guardian_exited"
                break
            write_json(
                OWNED / "heartbeat.json",
                {
                    "at": now().isoformat(),
                    "container_id": resource["container_id"],
                    "supervisor": resource["supervisor"],
                    "creator_token": resource["creator_token"],
                    "generation": resource["supervisor"]["start_ticks"],
                    "guardian_pid": guard.pid,
                },
            )
            time.sleep(5)
    finally:
        stop_owned(reason)


def heartbeat_failure(resource, heartbeat, elapsed_seconds):
    if now() >= datetime.fromisoformat(resource["deadline"]):
        return "guardian_deadline"
    if heartbeat is None or heartbeat.get("container_id") != resource["container_id"]:
        return "guardian_current_heartbeat_missing" if elapsed_seconds > 45 else None
    if heartbeat.get("supervisor") != resource["supervisor"]:
        return "guardian_heartbeat_supervisor_mismatch"
    if (
        heartbeat.get("creator_token") != resource["creator_token"]
        or heartbeat.get("generation") != resource["supervisor"]["start_ticks"]
    ):
        return "guardian_heartbeat_identity_mismatch"
    if (now() - datetime.fromisoformat(heartbeat["at"])).total_seconds() > 45:
        return "guardian_heartbeat_stale"
    return None


def guardian():
    resource = json.loads((OWNED / "resource.json").read_text())
    start_wait = time.monotonic()
    while True:
        if (OWNED / "termination.json").exists():
            return
        reason = None
        if now() >= datetime.fromisoformat(resource["deadline"]):
            reason = "guardian_deadline"
        try:
            identity = process_identity(resource["supervisor"]["pid"])
            if identity != resource["supervisor"]:
                reason = "guardian_supervisor_identity_changed"
        except (FileNotFoundError, ProcessLookupError):
            reason = "guardian_supervisor_lost"
        heartbeat = (
            json.loads((OWNED / "heartbeat.json").read_text())
            if (OWNED / "heartbeat.json").exists()
            else None
        )
        heartbeat_reason = heartbeat_failure(
            resource, heartbeat, time.monotonic() - start_wait
        )
        if heartbeat_reason:
            reason = heartbeat_reason
        if reason:
            stop_owned(reason)
            return
        time.sleep(5)


def snapshot():
    resource = json.loads((OWNED / "resource.json").read_text())
    container = inspect_container(resource["container_id"])
    assert_owned_container(container, resource)
    process = process_identity(container["state"]["Pid"])
    cgroup_path = Path("/sys/fs/cgroup") / process["cgroup"].split("::", 1)[1].lstrip(
        "/"
    )
    limits = {
        field: (cgroup_path / field).read_text().strip()
        for field in ("memory.max", "memory.swap.max", "cpu.max", "pids.max")
    }
    assert limits == {
        "memory.max": "1610612736",
        "memory.swap.max": "0",
        "cpu.max": "100000 100000",
        "pids.max": "128",
    }
    with urllib.request.urlopen("http://127.0.0.1:27474/", timeout=5) as response:
        http = {"status": response.status, "body": json.loads(response.read())}
    assert (
        http["status"] == 200
        and http["body"]["neo4j_version"] == "5.26.32"
        and http["body"]["neo4j_edition"] == "community"
    )
    with socket.create_connection(("127.0.0.1", 27687), timeout=5):
        pass
    result = {
        "at": now().isoformat(),
        "resource": resource,
        "container": container,
        "kernel_limits": limits,
        "http": http,
        "bolt_socket_ready": True,
        "bolt_authentication": "not_run",
    }
    write_json(OUTPUT / "snapshot.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "operation",
        choices=(
            "preflight",
            "pull",
            "verify_image",
            "supervise",
            "prepare_rebuild",
            "supervise_rebuild",
            "resume_stopped",
            "guardian",
            "snapshot",
            "stop",
        ),
    )
    parser.add_argument("--check", action="store_true")
    options = parser.parse_args()
    operations = {
        "preflight": preflight,
        "pull": pull,
        "verify_image": verify_image,
        "supervise": supervisor,
        "prepare_rebuild": prepare_rebuild,
        "supervise_rebuild": lambda: supervisor(existing_volume=True),
        "resume_stopped": resume_stopped,
        "guardian": guardian,
        "snapshot": snapshot,
        "stop": lambda: stop_owned("manual_owned", options.check),
    }
    result = operations[options.operation]()
    if result is not None:
        print(json.dumps(result))
