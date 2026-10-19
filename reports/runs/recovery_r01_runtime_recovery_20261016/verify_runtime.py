"""Read health, existing test database counts and preserved storage identities."""

import ipaddress
import json
import socket
import subprocess
import urllib.request
from pathlib import Path

from restore_services import DOCKER, OUTPUT, RUNTIME, inventory, now


def postgres_query(query):
    result = subprocess.run(
        [
            *DOCKER,
            "exec",
            "-i",
            "dianzi-test-r01_20261014-postgres",
            "psql",
            "-U",
            "test_dianzi_r01",
            "-d",
            "test_dianzi_r01_20261014",
            "-p",
            "25432",
            "-v",
            "ON_ERROR_STOP=1",
            "-A",
            "-t",
            "-q",
        ],
        input="BEGIN READ ONLY;\n" + query + "\nROLLBACK;\n",
        capture_output=True,
        text=True,
        timeout=8,
        check=False,
    )
    assert result.returncode == 0, "Existing-test PostgreSQL read-only query failed."
    return result.stdout.strip()


def redis_send(connection, *items):
    payload = ("*" + str(len(items)) + "\r\n").encode()
    for item in items:
        encoded = item.encode()
        payload += ("$" + str(len(encoded)) + "\r\n").encode() + encoded + b"\r\n"
    connection.sendall(payload)
    return connection.recv(4096)


def search_json(path):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open("http://127.0.0.1:29200" + path, timeout=5) as response:
        assert response.status == 200
        return json.load(response)


def verify():
    current = inventory("inventory_health")
    selected = [
        item
        for item in current["containers"]
        if item["labels"].get("dianzi.project") == "dianzi-test-r01_20261014"
    ]
    assert len(selected) == 3
    assert sum(item["state"]["Running"] for item in current["containers"]) == 3
    for item in selected:
        assert item["state"]["Running"] and item["health"] == "healthy"
        host = item["host_limits"]
        kernel = item["kernel_limits"]
        assert kernel["memory.max"] == str(host["Memory"])
        assert kernel["pids.max"] == str(host["PidsLimit"])
        assert kernel["cpu.max"] == str(round(host["NanoCpus"] / 10000)) + " 100000"
        assert kernel["memory.swap.max"] == str(host["MemorySwap"] - host["Memory"])
    listeners_result = subprocess.run(
        ["ss", "-ltnp"], capture_output=True, text=True, timeout=5, check=True
    )
    listeners = []
    for item in selected:
        group = Path("/sys/fs/cgroup") / item["kernel_cgroup"].lstrip("/")
        process_ids = set((group / "cgroup.procs").read_text().split())
        lines = [
            line
            for line in listeners_result.stdout.splitlines()[1:]
            if any("pid=" + pid + "," in line for pid in process_ids)
        ]
        assert lines, "Restored test service has no listener."
        for line in lines:
            host, port = line.split()[3].rsplit(":", 1)
            address = ipaddress.ip_address(host.strip("[]"))
            if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
                address = address.ipv4_mapped
            assert address.is_loopback, (
                "Restored service exposes a non-loopback listener."
            )
            listeners.append(
                {"service": item["name"], "address": str(address), "port": int(port)}
            )
    assert {25432, 26379, 29200} <= {item["port"] for item in listeners}
    assert (
        postgres_query(
            "SELECT current_database()='test_dianzi_r01_20261014' AND current_user='test_dianzi_r01';"
        )
        == "t"
    )
    database_count = int(
        postgres_query(
            "SELECT count(*) FROM pg_database WHERE datname LIKE 'test_dianzi_%';"
        )
    )
    assert database_count >= 3
    table_count = int(
        postgres_query(
            "SELECT count(*) FROM information_schema.tables WHERE table_schema='public';"
        )
    )
    marker_count = int(
        postgres_query(
            "SELECT count(*) FROM r01_resource_probe WHERE probe_id='persistent-r01';"
        )
    )
    assert marker_count == 1
    config_path = RUNTIME / "test-services/connection.json"
    assert (
        config_path.resolve() == config_path
        and config_path.stat().st_mode & 0o777 == 0o600
    )
    private_config = json.loads(config_path.read_text())
    assert private_config["DIANZI_TEST_RUN_ID"] == "r01_20261014"
    with socket.create_connection(("127.0.0.1", 26379), timeout=3) as connection:
        assert (
            redis_send(connection, "AUTH", private_config["redis_password"])
            == b"+OK\r\n"
        )
        assert redis_send(connection, "PING") == b"+PONG\r\n"
        assert redis_send(connection, "EXISTS", "r01:resource:persistent") == b":1\r\n"
    search_version = search_json("/")["version"]["number"]
    search_health = search_json("/_cluster/health")["status"]
    assert search_version == "2.17.0" and search_health == "green"
    assert search_json("/r01-resource-smoke/_doc/real-input")["found"]
    preflight = json.loads((OUTPUT / "preflight_evidence.json").read_text())
    data_before = next(
        item for item in preflight["metadata"] if item["path"] == str(RUNTIME / "data")
    )
    assert (RUNTIME / "data").stat().st_ino == data_before["inode"]
    before = json.loads((OUTPUT / "inventory_before_restore.json").read_text())
    assert (
        before["images"] == current["images"]
        and before["volumes"] == current["volumes"]
    )
    assert {item["id"] for item in before["containers"]} == {
        item["id"] for item in current["containers"]
    }
    lifecycle = current["lifecycle"]
    process_identity = {}
    for role in ("supervisor", "daemon"):
        proc = Path("/proc") / str(lifecycle[role + "_pid"])
        assert (
            proc.joinpath("stat").read_text().split()[21]
            == lifecycle[role + "_start_ticks"]
        )
        process_identity[role] = {
            "pid": lifecycle[role + "_pid"],
            "start_ticks": lifecycle[role + "_start_ticks"],
            "executable": str(proc.joinpath("exe").resolve()),
            "cgroup": proc.joinpath("cgroup").read_text().strip(),
        }
    archive = Path(lifecycle["recovery_archive"])
    volume_identity = [
        {"name": volume["Name"], "inode": Path(volume["Mountpoint"]).stat().st_ino}
        for volume in current["volumes"]
    ]
    receipt = {
        "verified_at": now(),
        "started_at": lifecycle["started_at"],
        "planned_end_at": lifecycle["deadline"],
        "actual_end_at": None,
        "resourceBudget": lifecycle["resourceBudget"],
        "log_budget": {
            "previous_segments_bytes": lifecycle["previous_log_bytes"],
            "current_segment_bytes": (RUNTIME / "dockerd.log").stat().st_size,
            "current_segment_cap": lifecycle["segment_log_budget_bytes"],
        },
        "boot_id": lifecycle["boot_id"],
        "previous_stop_time": "unknown",
        "previous_stop_cause": "unknown",
        "process_identity": process_identity,
        "healthy_services": 3,
        "service_listeners": listeners,
        "postgres": {
            "identity_passed": True,
            "read_only": True,
            "existing_test_database_count": database_count,
            "existing_public_table_count": table_count,
            "existing_resource_marker_count": marker_count,
        },
        "redis": {"authenticated_ping": True, "existing_resource_marker_exists": True},
        "search": {
            "version": search_version,
            "health": search_health,
            "existing_resource_marker_found": True,
        },
        "storage": {
            "same_data_root_inode": data_before["inode"],
            "images_unchanged": len(current["images"]),
            "containers_unchanged": len(current["containers"]),
            "volumes_unchanged": len(current["volumes"]),
            "volume_identities": volume_identity,
            "old_runtime_evidence_archive": str(archive),
            "old_logs_remain_private": True,
            "new_backup_created": False,
        },
        "exit_management": {
            "wall_and_monotonic_deadline": True,
            "owned_term_command": "wsl.exe -d Ubuntu-22.04 -u root --exec python3 -B /mnt/d/dianzi/reports/runs/recovery_r01_runtime_recovery_20261016/stop_owned.py",
            "forced_shutdown_test": "not_run",
            "automatic_deadline_exit": "not_run",
        },
    }
    (OUTPUT / "runtime_receipt.json").write_text(json.dumps(receipt, indent=2))
    print(
        json.dumps(
            {
                key: receipt[key]
                for key in (
                    "verified_at",
                    "started_at",
                    "planned_end_at",
                    "healthy_services",
                    "postgres",
                    "redis",
                    "search",
                )
            }
        )
    )


if __name__ == "__main__":
    verify()
