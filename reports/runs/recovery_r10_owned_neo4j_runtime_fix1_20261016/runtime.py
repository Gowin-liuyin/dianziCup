"""Operate only the explicitly authorised R10 Neo4j test resource."""

import hashlib
import json
import os
import signal
import socket
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

OWNED = Path("/tmp/dianzi-r10-neo4j-operations-fix1-20261016")
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
    "NEO4J_dbms_usage__report_enabled": "false",
}
DEADLINE = "2026-10-16T19:35:43.312788+08:00"
CREATOR = "1c406c2c-8349-48ed-af73-482936223968"
RUNTIME_GENERATION = "r10-owned-runtime-fix1-20261016"
CAPABILITIES = {"CHOWN", "SETUID", "SETGID", "DAC_OVERRIDE", "FOWNER", "KILL"}
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
    assert resource["runtime_generation"] == RUNTIME_GENERATION
    assert labels["dianzi.runtime_generation"] == RUNTIME_GENERATION
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
        result["docker_exit_code"] = 0
        result["container_exit_code"] = stopped["state"]["ExitCode"]
        result["bounded_stop"] = "passed"
        result["graceful_shutdown"] = (
            "exit_zero_pending_shutdown_log"
            if stopped["state"]["ExitCode"] == 0
            else "failed"
        )
    if not check:
        write_json(OWNED / "termination.json", result)
        write_json(OUTPUT / "termination.json", result)
    return result


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
                    "runtime_generation": resource["runtime_generation"],
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
    if heartbeat.get("runtime_generation") != resource["runtime_generation"]:
        return "guardian_heartbeat_runtime_generation_mismatch"
    if (now() - datetime.fromisoformat(heartbeat["at"])).total_seconds() > 45:
        return "guardian_heartbeat_stale"
    return None


def start_supervisor():
    resource = json.loads((OWNED / "resource.json").read_text())
    assert resource["deadline"] == DEADLINE and now() < datetime.fromisoformat(DEADLINE)
    assert resource["creator_token"] == CREATOR
    container = inspect_container(resource["container_id"])
    assert_owned_container(container, resource)
    assert not container["state"]["Running"]
    if "supervisor" in resource:
        for name in ("supervisor", "guardian"):
            try:
                observed = process_identity(resource[name]["pid"])
            except (FileNotFoundError, ProcessLookupError):
                continue
            assert observed != resource[name], "Previous generation is active"
        archive = OWNED / ("ended_generation_" + resource["supervisor"]["start_ticks"])
        archive.mkdir(mode=0o700)
        for name in ("resource.json", "heartbeat.json", "termination.json"):
            source = OWNED / name
            assert source.resolve() == source and source.parent == OWNED
            source.rename(archive / name)
        resource.pop("container_process")
        resource.pop("guardian")
        resource.pop("started_at")
    for port in (27687, 27474):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", port))
    resource["supervisor"] = process_identity(os.getpid())
    write_json(OWNED / "resource.json", resource)
    run_supervision(resource)


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


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=("start", "guardian", "stop"))
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    if arguments.operation == "start":
        start_supervisor()
    elif arguments.operation == "guardian":
        guardian()
    else:
        print(json.dumps(stop_owned("manual_owned", arguments.check)))
