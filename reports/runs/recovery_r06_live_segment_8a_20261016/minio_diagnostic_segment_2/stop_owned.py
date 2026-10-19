"""Validate this Linux boot and cgroup before requesting this MinIO segment to stop."""

import argparse
import json
from pathlib import Path

RUN = Path("/mnt/d/dianzi/reports/runs/recovery_r06_live_segment_8a_20261016/minio_diagnostic_segment_2")
parser = argparse.ArgumentParser()
parser.add_argument("--check", action="store_true")
check_only = parser.parse_args().check
start = json.loads((RUN / "minio_start.json").read_text())
assert Path("/proc/sys/kernel/random/boot_id").read_text().strip() == start["boot_id"]
assert not (RUN / "minio_end.json").exists()
for name in ("supervisor", "child"):
    expected = start[name]
    process = Path("/proc") / str(expected["pid"])
    assert process.joinpath("stat").read_text().split()[21] == expected["start_ticks"]
    assert str(process.joinpath("exe").resolve()) == expected["executable"]
    assert process.joinpath("cgroup").read_text().strip() == expected["cgroup"]
group = Path(start["cgroup"])
assert group.resolve() == Path("/sys/fs/cgroup/dianzi-r01-20261014/minio-r06-live-8a-diag2-20261016")
assert set(group.joinpath("cgroup.procs").read_text().split()) == {str(start[name]["pid"]) for name in ("supervisor", "child")}
if not check_only:
    (RUN / "minio_stop.request").write_text("owned Linux boot and processes checked\n")
print(json.dumps({"operation": "minio_identity_checked" if check_only else "minio_stop_requested", "boot_id": start["boot_id"], "supervisor_pid": start["supervisor"]["pid"], "signals_sent": 0}))
