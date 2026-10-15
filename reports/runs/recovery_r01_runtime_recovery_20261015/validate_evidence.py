"""Check saved recovery evidence and read the still-running supervisor identities."""

import ast
import hashlib
import json
import os
import sys
from datetime import datetime
from pathlib import Path

sys.dont_write_bytecode = True
from verify_recovery import parse_postgres_observation

output = Path(__file__).resolve().parent
runtime = Path("/tmp/dianzi-docker-static-r01-20261014/runtime")
sources = sorted(output.glob("*.py"))
for source in sources:
    ast.parse(source.read_text())
assert parse_postgres_observation("2026-10-15 02:04:55.205759+00").microsecond == 205759
assert (
    parse_postgres_observation("2026-10-15 02:05:25.21959+00:00").microsecond == 219590
)
preparation = json.loads((output / "preparation_evidence.json").read_text())
archive = Path(preparation["private_archive"])
assert archive.resolve() == archive and archive.parent == runtime.parent
previous = json.loads((archive / "lifecycle.json").read_text())
assert (
    previous["ended_at"] is None and previous["deadline"] == "2026-10-17T21:49:15+08:00"
)
assert (archive / "lifecycle.json").read_bytes() == (
    output / "previous_lifecycle.json"
).read_bytes()
for item in preparation["archive_metadata"]:
    if "sha256" in item:
        archived = Path(item["archive"]["path"])
        assert archived.parent == archive
        assert hashlib.sha256(archived.read_bytes()).hexdigest() == item["sha256"]
before = json.loads((output / "preflight_evidence.json").read_text())
after = json.loads((output / "inventory_after_restore_retry_1.json").read_text())
assert {item["id"] for item in before["persisted_containers"]} == {
    item["id"] for item in after["containers"]
}
operations = json.loads((output / "restore_operations.json").read_text())
assert len(operations) == 14 and not any(
    "r01_tls_" in item["name"] for item in operations
)
assert all(
    item["exit_code"] == 0 and item["operation"] == "start" for item in operations
)
current = json.loads((runtime / "lifecycle.json").read_text())
assert current["ended_at"] is None and current["deadline"] == previous["deadline"]
assert current["command"] == previous["command"]
processes = []
for key in ("supervisor_pid", "daemon_pid"):
    pid = current[key]
    proc = Path("/proc") / str(pid)
    assert proc.exists()
    fields = (proc / "stat").read_text().rsplit(")", 1)[1].split()
    cgroup = (proc / "cgroup").read_text().strip()
    assert cgroup == "0::/dianzi-r01-20261014/supervisor"
    processes.append(
        {
            "role": key,
            "pid": pid,
            "parent_pid": int(fields[1]),
            "start_ticks": int(fields[19]),
            "executable": os.readlink(proc / "exe"),
            "cgroup": cgroup,
        }
    )
limits = {
    name: (Path(current["cgroup"]) / name).read_text().strip()
    for name in ("memory.max", "memory.swap.max", "cpu.max", "pids.max")
}
assert limits == {
    "memory.max": "8589934592",
    "memory.swap.max": "2147483648",
    "cpu.max": "200000 100000",
    "pids.max": "2048",
}
record = {
    "validated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    "python_version": sys.version.split()[0],
    "source_syntax_count": len(sources),
    "parser_self_checks": {"passed": 2, "failed": 0, "skipped": 0},
    "old_stop_time": "unknown",
    "old_boot_id": "not_recorded_in_prior_lifecycle",
    "current_boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
    "processes": processes,
    "parent_limits": limits,
    "deadline": current["deadline"],
    "old_lifecycle_and_log_hashes_preserved": True,
    "full_container_ids_preserved": 17,
    "restore_starts": 14,
    "tls_not_started_by_this_script": True,
    "source_sha256": {
        source.name: hashlib.sha256(source.read_bytes()).hexdigest()
        for source in sources
    },
    "launched_supervisor_sha256": hashlib.sha256(
        (output / "launched_supervisor.py.txt").read_bytes()
    ).hexdigest(),
    "original_reused_source_sha256": {
        name: hashlib.sha256(
            (
                output.parent / "recovery_r01_socket_root_cause_20261014" / name
            ).read_bytes()
        ).hexdigest()
        for name in ("supervise_isolated_daemon.py", "delegate_project_controllers.py")
    },
}
(output / "evidence_validation.json").write_text(json.dumps(record, indent=2))
print(
    json.dumps(
        {
            "validated_at": record["validated_at"],
            "source_syntax_count": len(sources),
            "parser_self_checks_passed": 2,
            "archive_hashes": "preserved",
            "deadline": current["deadline"],
            "supervisor_and_daemon_alive": True,
        }
    )
)
