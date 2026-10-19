"""Restore only previously running, labelled project containers without recreating data."""

import argparse
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path

CACHE = Path("/tmp/dianzi-docker-static-r01-20261014")
RUNTIME = CACHE / "runtime"
OUTPUT = Path(__file__).resolve().parent
DOCKER = [
    str(CACHE / "portable/docker/docker"),
    "--config",
    str(RUNTIME / "client-config"),
    "--host",
    "unix://" + str(RUNTIME / "docker.sock"),
]
BARE_PROJECTS = (
    "dianzi-test-r01_20261014",
    "dianzi-test-r01_quality_20261014",
    "dianzi-test-r01_frontend_20261014",
)
INFRA_PROJECT = "dianzi-test-r01_infra_20261015"
TLS_PROJECT = "dianzi-test-r01_tls_20261015"
FIELDS = ("memory.max", "memory.swap.max", "cpu.max", "pids.max")


def now():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def docker(arguments):
    result = subprocess.run(
        DOCKER + arguments, capture_output=True, text=True, timeout=25, check=False
    )
    assert result.returncode == 0, "Docker operation failed: " + " ".join(arguments[:2])
    return result.stdout


def selected_container(container):
    state = container["State"]
    host = container["HostConfig"]
    pid = state["Pid"]
    kernel_group = None
    kernel_limits = None
    if state["Running"] and pid:
        lines = Path("/proc/" + str(pid) + "/cgroup").read_text().splitlines()
        kernel_group = next(
            line.split(":", 2)[2] for line in lines if line.startswith("0::")
        )
        assert kernel_group.startswith("/dianzi-r01-20261014/"), (
            "Container escaped its parent."
        )
        group = Path("/sys/fs/cgroup") / kernel_group.lstrip("/")
        kernel_limits = {name: (group / name).read_text().strip() for name in FIELDS}
    return {
        "id": container["Id"],
        "name": container["Name"],
        "image_id": container["Image"],
        "labels": container["Config"].get("Labels") or {},
        "state": {
            key: state.get(key)
            for key in (
                "Running",
                "Paused",
                "Pid",
                "ExitCode",
                "StartedAt",
                "FinishedAt",
            )
        },
        "health": (state.get("Health") or {}).get("Status"),
        "mounts": [
            {
                key: mount.get(key)
                for key in ("Type", "Name", "Source", "Destination", "RW")
            }
            for mount in container["Mounts"]
        ],
        "host_limits": {
            key: host.get(key)
            for key in ("Memory", "MemorySwap", "NanoCpus", "PidsLimit")
        },
        "network_mode": host["NetworkMode"],
        "cgroup_parent": host["CgroupParent"],
        "restart_policy": host["RestartPolicy"],
        "log_config": host["LogConfig"],
        "kernel_cgroup": kernel_group,
        "kernel_limits": kernel_limits,
    }


def inventory(label):
    ids = docker(["ps", "-aq"]).split()
    containers = [
        selected_container(container)
        for container in json.loads(docker(["inspect", *ids]))
    ]
    image_ids = docker(["image", "ls", "-aq"]).split()
    images = [
        {
            "id": image["Id"],
            "repo_tags": image.get("RepoTags"),
            "repo_digests": image.get("RepoDigests"),
        }
        for image in json.loads(docker(["image", "inspect", *sorted(set(image_ids))]))
    ]
    names = docker(["volume", "ls", "-q"]).split()
    volumes = [
        {
            key: volume.get(key)
            for key in ("Name", "Driver", "Mountpoint", "Labels", "CreatedAt")
        }
        for volume in json.loads(docker(["volume", "inspect", *names]))
    ]
    lifecycle = json.loads((RUNTIME / "lifecycle.json").read_text())
    assert (
        lifecycle["deadline"] == "2026-10-17T21:49:15+08:00"
        and lifecycle["ended_at"] is None
    )
    for key in ("supervisor_pid", "daemon_pid"):
        pid = lifecycle[key]
        assert Path("/proc/" + str(pid)).exists()
    info = json.loads(docker(["info", "--format", "{{json .}}"]))
    group = Path("/sys/fs/cgroup/dianzi-r01-20261014")
    record = {
        "at": now(),
        "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
        "lifecycle": lifecycle,
        "daemon": {
            key: info.get(key)
            for key in (
                "ServerVersion",
                "DockerRootDir",
                "CgroupDriver",
                "CgroupVersion",
                "LoggingDriver",
                "Containers",
                "ContainersRunning",
                "ContainersStopped",
                "Images",
            )
        },
        "project_limits": {name: (group / name).read_text().strip() for name in FIELDS},
        "parent_and_sibling_limits": json.loads(
            (OUTPUT / "preparation_evidence.json").read_text()
        )["existing_parent_and_sibling_limits_after"],
        "containers": containers,
        "images": images,
        "volumes": volumes,
        "unix_socket_metadata": {
            "uid": (RUNTIME / "docker.sock").stat().st_uid,
            "mode": oct((RUNTIME / "docker.sock").stat().st_mode & 0o777),
        },
    }
    destination = OUTPUT / (label + ".json")
    assert not destination.exists(), "Do not overwrite an earlier inventory."
    destination.write_text(json.dumps(record, indent=2))
    print(
        json.dumps(
            {
                "at": record["at"],
                "inventory": label,
                "containers": len(containers),
                "running": sum(item["state"]["Running"] for item in containers),
                "images": len(images),
                "volumes": len(volumes),
                "deadline": lifecycle["deadline"],
                "supervisor_pid": lifecycle["supervisor_pid"],
                "daemon_pid": lifecycle["daemon_pid"],
            }
        )
    )
    return record


def restore():
    before = inventory("inventory_before_restore")
    persisted = json.loads((OUTPUT / "preflight_evidence.json").read_text())[
        "persisted_containers"
    ]
    by_id = {item["id"]: item for item in before["containers"]}
    selected = []
    for item in persisted:
        assert item["id"] in by_id and item["name"] == by_id[item["id"]]["name"]
        current = by_id[item["id"]]
        assert item["image_id"] == current["image_id"]
        assert item["labels"] == current["labels"]
        if not item["state"]["Running"]:
            continue
        labels = item["labels"] or {}
        project = labels.get("dianzi.project") or labels.get(
            "com.docker.compose.project"
        )
        if project != "dianzi-test-r01_20261014":
            continue
        assert project in (*BARE_PROJECTS, INFRA_PROJECT)
        if project in BARE_PROJECTS:
            assert labels["dianzi.mode"] == "test"
            assert item["name"].lstrip("/") in [
                project + "-" + role for role in ("postgres", "redis", "opensearch")
            ]
        else:
            assert labels["com.docker.compose.service"] in (
                "postgres",
                "redis",
                "opensearch",
                "api",
                "worker",
                "scheduler",
                "frontend",
            )
            assert (
                item["name"].lstrip("/")
                == project + "-" + labels["com.docker.compose.service"] + "-1"
            )
        assert current["network_mode"] == "host"
        assert current["cgroup_parent"] in ("", "/dianzi-r01-20261014")
        if not current["cgroup_parent"]:
            command = before["lifecycle"]["command"]
            assert project == INFRA_PROJECT
            assert "--cgroup-parent=/dianzi-r01-20261014" in command
        assert current["restart_policy"]["Name"] == "no"
        selected.append(current)
    assert len(selected) == 3, "Require exactly the three original root test services."
    order = {
        "postgres": 0,
        "redis": 1,
        "opensearch": 2,
        "api": 3,
        "worker": 4,
        "scheduler": 5,
        "frontend": 6,
    }
    selected.sort(
        key=lambda item: order.get(
            (
                item["labels"].get("com.docker.compose.service")
                or item["name"].rsplit("-", 1)[-1]
            ),
            99,
        )
    )
    operations = []
    for item in selected:
        if item["state"]["Running"]:
            operations.append(
                {"id": item["id"], "name": item["name"], "operation": "already_running"}
            )
            continue
        started = now()
        docker(["start", item["id"]])
        observed = selected_container(json.loads(docker(["inspect", item["id"]]))[0])
        assert observed["state"]["Running"] and observed["kernel_cgroup"].startswith(
            "/dianzi-r01-20261014/"
        )
        operations.append(
            {
                "id": item["id"],
                "name": item["name"],
                "operation": "start",
                "started_at": started,
                "ended_at": now(),
                "exit_code": 0,
            }
        )
        (OUTPUT / "restore_operations.json").write_text(
            json.dumps(operations, indent=2)
        )
    after = inventory("inventory_after_restore")
    assert {item["id"] for item in before["containers"]} == {
        item["id"] for item in after["containers"]
    }
    assert before["images"] == after["images"] and before["volumes"] == after["volumes"]
    print(
        json.dumps(
            {
                "selected_existing_containers": len(selected),
                "started": sum(item["operation"] == "start" for item in operations),
                "data_recreated": False,
                "tls_excluded": True,
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=("inventory", "restore"))
    operation = parser.parse_args().operation
    assert os.getuid() == 0
    if operation == "restore":
        restore()
    else:
        inventory("inventory_current")
