"""Check original archives and new evidence without exposing private connection values."""

import ast
import hashlib
import json
import os
from pathlib import Path

from restore_services import OUTPUT, RUNTIME, now

preparation = json.loads((OUTPUT / "preparation_evidence.json").read_text())
archive = Path(preparation["private_archive"])
assert archive.parent == Path("/tmp/dianzi-docker-static-r01-20261014")
archive_checks = []
for item in preparation["archive_metadata"]:
    target = Path(item["archive"]["path"])
    assert target.parent == archive and target.resolve() == target
    if "sha256" in item:
        assert hashlib.sha256(target.read_bytes()).hexdigest() == item["sha256"]
    else:
        assert target.lstat().st_ino == item["source"]["inode"]
    archive_checks.append(target.name)
sources = list(OUTPUT.glob("*.py"))
for source in sources:
    ast.parse(source.read_text())
ast.parse((OUTPUT / "launched_supervisor.py.txt").read_text())
private = json.loads((RUNTIME / "test-services/connection.json").read_text())
secret_values = [
    str(value).encode()
    for key, value in private.items()
    if "password" in key.lower() or key in ("TEST_DATABASE_URL", "TEST_REDIS_URL")
]
secret_values += [
    value.encode()
    for key, value in os.environ.items()
    if key.lower() in ("http_proxy", "https_proxy") and len(value) >= 8
]
assert all(secret_values)
scanned_files = 0
for path in [
    *OUTPUT.iterdir(),
    OUTPUT.parent.parent / "tasks/R01-runtime-recovery-20261016.md",
]:
    if path.is_file():
        contents = path.read_bytes()
        assert not any(value in contents for value in secret_values), (
            "Private value appears in delivery artifact."
        )
        scanned_files += 1
operations = json.loads((OUTPUT / "restore_operations.json").read_text())
assert len(operations) == 3 and all(item["operation"] == "start" for item in operations)
receipt = json.loads((OUTPUT / "runtime_receipt.json").read_text())
assert receipt["healthy_services"] == 3
lifecycle = json.loads((RUNTIME / "lifecycle.json").read_text())
assert lifecycle["ended_at"] is None and lifecycle["recovery_segment"] == "20261016"
assert (
    lifecycle["boot_id"] == Path("/proc/sys/kernel/random/boot_id").read_text().strip()
)
for role in ("supervisor", "daemon"):
    proc = Path("/proc") / str(lifecycle[role + "_pid"])
    assert (
        proc.joinpath("stat").read_text().split()[21]
        == lifecycle[role + "_start_ticks"]
    )
record = {
    "verified_at": now(),
    "archive_original_bytes_checked": archive_checks,
    "python_sources_parsed": len(sources),
    "launched_source_parsed": True,
    "private_values_present": False,
    "public_files_scanned": scanned_files,
    "supervisor_alive": True,
    "daemon_alive": True,
    "launched_supervisor_sha256": hashlib.sha256(
        (OUTPUT / "launched_supervisor.py.txt").read_bytes()
    ).hexdigest(),
    "resource_window_ends_at": lifecycle["deadline"],
    "acceptance": "not_assessed",
}
(OUTPUT / "delivery_validation.json").write_text(json.dumps(record, indent=2))
print(json.dumps(record))
