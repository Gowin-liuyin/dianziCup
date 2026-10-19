"""Inspect owned process privileges and exact kernel listener addresses read-only."""

import ipaddress
import json
import os
from pathlib import Path

import importlib.util
import sys

runtime_path = '/mnt/d/dianzi/reports/runs/recovery_r10_owned_neo4j_runtime_fix1_20261016/runtime.py'
spec = importlib.util.spec_from_file_location('runtime', runtime_path)
runtime = importlib.util.module_from_spec(spec)
sys.modules['runtime'] = runtime
spec.loader.exec_module(runtime)
runtime.OUTPUT = Path(__file__).resolve().parent

resource = json.loads((runtime.OWNED / "resource.json").read_text())
assert resource["container_id"] == "2cbf8058a220f4b3bc0d4da779f06ddaa314f7a87feeac32ab64b18d0735bf99"
assert resource["deadline"] == "2026-10-16T19:35:43.312788+08:00"
assert runtime.now() < runtime.datetime.fromisoformat(resource["deadline"])
container = runtime.inspect_container(resource["container_id"])
runtime.assert_owned_container(container, resource)
assert container["state"]["Running"]
identity = runtime.process_identity(container["state"]["Pid"])
cgroup = Path("/sys/fs/cgroup") / identity["cgroup"].split("::", 1)[1].lstrip("/")
pids = [int(value) for value in (cgroup / "cgroup.procs").read_text().split()]
processes = []
socket_inodes = set()
for pid in pids:
    process = Path("/proc") / str(pid)
    status = dict(
        line.split(":", 1)
        for line in process.joinpath("status").read_text().splitlines()
        if ":" in line
    )
    entry = {
        "pid": pid,
        "name": status["Name"].strip(),
        "uids": status["Uid"].split(),
        "gids": status["Gid"].split(),
        "cap_effective": status["CapEff"].strip(),
        "cap_bounding": status["CapBnd"].strip(),
        "no_new_privileges": status["NoNewPrivs"].strip(),
        "seccomp": status["Seccomp"].strip(),
    }
    processes.append(entry)
    for descriptor in process.joinpath("fd").iterdir():
        try:
            target = os.readlink(descriptor)
        except FileNotFoundError:
            continue
        if target.startswith("socket:["):
            socket_inodes.add(target[8:-1])
java = [entry for entry in processes if entry["name"] == "java"]
assert len(java) == 1 and java[0]["uids"] == ["7474"] * 4
assert java[0]["cap_effective"] == "0000000000000000"
assert all(entry["cap_bounding"] == "00000000000000eb" for entry in processes)
assert (
    next(entry for entry in processes if entry["name"] == "tini")["cap_effective"]
    == "00000000000000eb"
)
assert os.readlink(
    Path("/proc") / str(container["state"]["Pid"]) / "ns/pid"
) != os.readlink("/proc/self/ns/pid")
assert all(
    entry["no_new_privileges"] == "1" and entry["seccomp"] == "2" for entry in processes
)
listeners = []
for table in ("tcp", "tcp6"):
    for line in Path("/proc/net", table).read_text().splitlines()[1:]:
        fields = line.split()
        if fields[3] == "0A" and fields[9] in socket_inodes:
            address_hex, port_hex = fields[1].split(":")
            encoded_address = bytes.fromhex(address_hex)
            network_bytes = b"".join(
                encoded_address[index : index + 4][::-1]
                for index in range(0, len(encoded_address), 4)
            )
            address = ipaddress.ip_address(network_bytes)
            if (
                isinstance(address, ipaddress.IPv6Address)
                and address.ipv4_mapped is not None
            ):
                address = address.ipv4_mapped
            listeners.append(
                {
                    "table": table,
                    "local_address_hex": fields[1],
                    "local_address": str(address),
                    "port": int(port_hex, 16),
                    "socket_inode": fields[9],
                }
            )
assert {(entry["local_address"], entry["port"]) for entry in listeners} == {
    ("127.0.0.1", 27687),
    ("127.0.0.1", 27474),
}
assert not (runtime.OWNED / "neo4j-auth.env").exists()
assert container["memory"] == container["memory_swap"] == 1610612736
assert container["nano_cpus"] == 1000000000 and container["pids_limit"] == 128
assert {
    value.removeprefix("CAP_") for value in container["cap_add"]
} == runtime.CAPABILITIES
limits = {
    field: (cgroup / field).read_text().strip()
    for field in ("memory.max", "memory.swap.max", "cpu.max", "pids.max")
}
assert limits == {
    "memory.max": "1610612736",
    "memory.swap.max": "0",
    "cpu.max": "100000 100000",
    "pids.max": "128",
}
assert Path(resource["volume_mountpoint"]).stat().st_ino == 701675
result = {
    "kernel_limits": limits,
    "container_whitelist": container,
    "at": runtime.now().isoformat(),
    "container_id": resource["container_id"],
    "processes": processes,
    "listeners": listeners,
    "credential_envfile_removed": True,
    "volume_inode": 701675,
    "privileges_and_loopback": "passed",
}
runtime.write_json(runtime.OUTPUT / "kernel_security.json", result)
print(json.dumps(result))
