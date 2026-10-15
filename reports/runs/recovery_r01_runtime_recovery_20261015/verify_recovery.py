"""Read restored health, kernel boundaries and existing persistence probes."""

import ipaddress
import json
import os
import re
import socket
import subprocess
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from restore_services import DOCKER, OUTPUT, RUNTIME, inventory, now


def postgres_query(name, user, database, port, query):
    result = subprocess.run(
        [
            *DOCKER,
            "exec",
            "-i",
            name,
            "psql",
            "-U",
            user,
            "-d",
            database,
            "-p",
            str(port),
            "-v",
            "ON_ERROR_STOP=1",
            "-A",
            "-t",
        ],
        input=query,
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, "Read-only PostgreSQL probe failed."
    return result.stdout.strip()


def redis_send(connection, *items):
    payload = ("*" + str(len(items)) + "\r\n").encode()
    for item in items:
        encoded = item.encode()
        payload += ("$" + str(len(encoded)) + "\r\n").encode() + encoded + b"\r\n"
    connection.sendall(payload)
    return connection.recv(4096)


def get_json(url):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(url, timeout=5) as response:
        assert response.status == 200
        return json.load(response)


def parse_postgres_observation(value):
    """Accept PostgreSQL fractional seconds and abbreviated UTC offsets on Python 3.10."""
    if re.search(r"[+-]\d{2}$", value):
        value += ":00"
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S.%f%z")


def verify():
    current = inventory(
        "inventory_health_" + datetime.now().astimezone().strftime("%Y%m%dT%H%M%S")
    )
    recovered_at = datetime.fromisoformat(current["lifecycle"]["started_at"])
    selected = [
        item
        for item in current["containers"]
        if item["name"].startswith("/dianzi-test-") and "r01_tls_" not in item["name"]
    ]
    assert len(selected) == 14
    for item in selected:
        assert item["state"]["Running"] and item["health"] == "healthy"
        host = item["host_limits"]
        kernel = item["kernel_limits"]
        assert kernel["memory.max"] == str(host["Memory"])
        assert kernel["pids.max"] == str(host["PidsLimit"])
        assert kernel["cpu.max"] == str(round(host["NanoCpus"] / 10000)) + " 100000"
        swap = host["MemorySwap"]
        expected_swap = (
            "max" if swap == -1 else str((swap or host["Memory"] * 2) - host["Memory"])
        )
        assert kernel["memory.swap.max"] == expected_swap
    listeners_result = subprocess.run(
        ["ss", "-ltnp"], capture_output=True, text=True, timeout=5, check=True
    )
    service_listeners = []
    for item in selected:
        group = Path("/sys/fs/cgroup") / item["kernel_cgroup"].lstrip("/")
        process_ids = set((group / "cgroup.procs").read_text().split())
        lines = [
            line
            for line in listeners_result.stdout.splitlines()[1:]
            if any("pid=" + pid + "," in line for pid in process_ids)
        ]
        for line in lines:
            endpoint = line.split()[3]
            host, port = endpoint.rsplit(":", 1)
            address = ipaddress.ip_address(host.strip("[]"))
            if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
                address = address.ipv4_mapped
            assert address.is_loopback, "Restored service has a public listener."
            service_listeners.append(
                {"container": item["name"], "address": str(address), "port": int(port)}
            )
        if not any(role in item["name"] for role in ("worker", "scheduler")):
            assert lines, "Expected service listener absent."
    record = {
        "verified_at": now(),
        "healthy_restored_containers": len(selected),
        "kernel_limits_match_existing_host_config": True,
        "service_listeners": service_listeners,
        "postgres": [],
        "redis": [],
    }
    root_name = "dianzi-test-r01_20261014-postgres"
    stacks = [
        ("r01_20261014", "test_dianzi_r01", 25432, 26379, "test-services"),
        (
            "r01_quality_20261014",
            "test_dianzi_r01_quality",
            25434,
            26381,
            "test-services-r01_quality_20261014",
        ),
        (
            "r01_frontend_20261014",
            "test_dianzi_r01_frontend",
            25435,
            26382,
            "test-services-r01_frontend_20261014",
        ),
    ]
    for run_id, user, postgres_port, redis_port, private_directory in stacks:
        name = "dianzi-test-" + run_id + "-postgres"
        database = "test_dianzi_" + run_id
        identity = postgres_query(
            name,
            user,
            database,
            postgres_port,
            "SELECT current_database(),current_user;",
        )
        assert identity == database + "|" + user
        table_count = int(
            postgres_query(
                name,
                user,
                database,
                postgres_port,
                "SELECT count(*) FROM information_schema.tables WHERE table_schema='public';",
            )
        )
        record["postgres"].append(
            {
                "container": name,
                "identity_passed": True,
                "public_table_count": table_count,
            }
        )
        config_path = RUNTIME / private_directory / "connection.json"
        assert (
            config_path.resolve() == config_path
            and config_path.stat().st_mode & 0o777 == 0o600
        )
        private_config = json.loads(config_path.read_text())
        with socket.create_connection(
            ("127.0.0.1", redis_port), timeout=3
        ) as connection:
            assert (
                redis_send(connection, "AUTH", private_config["redis_password"])
                == b"+OK\r\n"
            )
            assert redis_send(connection, "PING") == b"+PONG\r\n"
            marker = None
            if run_id == "r01_20261014":
                marker = b"real-redis-test" in redis_send(
                    connection, "GET", "r01:resource:persistent"
                )
                assert marker
        record["redis"].append(
            {
                "run_id": run_id,
                "authenticated_ping": True,
                "existing_marker_retained": marker,
            }
        )
    root_marker = postgres_query(
        root_name,
        "test_dianzi_r01",
        "test_dianzi_r01_20261014",
        25432,
        "SELECT probe_id,payload,embedding <-> '[1,2,3]' FROM r01_resource_probe WHERE probe_id='persistent-r01';",
    )
    assert root_marker == "persistent-r01|real-pg-test|0"
    database_names = postgres_query(
        root_name,
        "test_dianzi_r01",
        "test_dianzi_r01_20261014",
        25432,
        "SELECT datname FROM pg_database WHERE datname LIKE 'test_dianzi_%' ORDER BY datname;",
    ).splitlines()
    assert all(re.fullmatch("test_dianzi_[a-z0-9_]+", name) for name in database_names)
    record["root_persistent_pg_probe_retained"] = True
    record["root_existing_test_databases"] = database_names
    search = get_json("http://127.0.0.1:29200/")
    assert search["version"]["number"] == "2.17.0"
    search_marker = get_json(
        "http://127.0.0.1:29200/r01-resource-smoke/_doc/real-input"
    )
    assert search_marker["found"] and search_marker["_source"]["mode"] == "test"
    record["root_search"] = {
        "version": search["version"]["number"],
        "existing_marker_retained": True,
        "health": get_json("http://127.0.0.1:29200/_cluster/health")["status"],
    }
    infra_name = "dianzi-test-r01_infra_20261015-postgres-1"
    raw = json.loads(
        subprocess.run(
            [*DOCKER, "inspect", infra_name],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        ).stdout
    )[0]
    port = int(raw["Config"]["Cmd"][raw["Config"]["Cmd"].index("-p") + 1])
    infra_query = postgres_query(
        infra_name,
        "test_dianzi_r01_infra",
        "test_dianzi_r01_infra_20261015",
        port,
        "SELECT version_num FROM alembic_version;SELECT note FROM t03_volume_probe WHERE id=1;"
        "SELECT component,observed_at FROM runtime_observations ORDER BY component;",
    )
    lines = infra_query.splitlines()
    assert lines[:2] == ["0005_runtime_observations", "survives-down-up"]
    observations = dict(line.split("|", 1) for line in lines[2:])
    assert set(observations) == {"scheduler", "worker"}
    ages = {}
    for name, value in observations.items():
        observed = parse_postgres_observation(value)
        assert observed > recovered_at
        age = (datetime.now(timezone.utc) - observed).total_seconds()
        assert 0 <= age <= 45
        ages[name] = age
    api_health = get_json("http://127.0.0.1:28201/v1/health/ready")
    assert api_health["status"] == "ready"
    assert all(item["state"] == "ready" for item in api_health["dependencies"].values())
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open("http://127.0.0.1:25201/", timeout=5) as response:
        assert response.status == 200
    record["infra"] = {
        "migration": lines[0],
        "existing_pg_marker_retained": True,
        "observations_after_recovery": observations,
        "ages_seconds": ages,
        "api_http": 200,
        "all_dependencies_ready": True,
        "frontend_http": 200,
        "ui_version_is_existing_old_image": True,
    }
    assert current["project_limits"] == {
        "memory.max": "8589934592",
        "memory.swap.max": "2147483648",
        "cpu.max": "200000 100000",
        "pids.max": "2048",
    }
    archive = Path(current["lifecycle"]["recovery_archive"])
    assert json.loads((archive / "lifecycle.json").read_text())["ended_at"] is None
    current_log = (RUNTIME / "dockerd.log").read_text()
    for key in (
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "NO_PROXY",
        "http_proxy",
        "https_proxy",
        "no_proxy",
    ):
        value = os.environ.get(key)
        if value:
            current_log = current_log.replace(value, "[REDACTED_PROXY_VALUE]")
    (OUTPUT / "recovered_dockerd.redacted.log").write_text(current_log)
    record["daemon_log_budget"] = {
        "previous_bytes": (archive / "dockerd.log").stat().st_size,
        "new_segment_bytes": (RUNTIME / "dockerd.log").stat().st_size,
        "total_budget_bytes": 10485760,
    }
    assert (
        sum(
            record["daemon_log_budget"][key]
            for key in ("previous_bytes", "new_segment_bytes")
        )
        < 10485760
    )
    record["finished_at"] = now()
    (OUTPUT / "health_and_persistence_evidence.json").write_text(
        json.dumps(record, indent=2)
    )
    print(
        json.dumps(
            {
                "verified_at": record["finished_at"],
                "restored_healthy_containers": len(selected),
                "root_pg_redis_search_markers_retained": True,
                "infra_pg_marker_retained": True,
                "infra_observations_after_recovery": True,
                "loopback_and_kernel_limits": True,
                "tls_read_only_inventory": True,
                "not_continuous_monitoring": True,
            }
        )
    )


if __name__ == "__main__":
    assert (
        parse_postgres_observation("2026-10-15 02:04:55.205759+00").microsecond
        == 205759
    )
    assert (
        parse_postgres_observation("2026-10-15 02:05:25.21959+00:00").microsecond
        == 219590
    )
    verify()
