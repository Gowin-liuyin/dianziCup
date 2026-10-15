"""Apply the specifically authorized temporary root delegation without changing existing limits."""

import json
import os
from datetime import datetime
from pathlib import Path


root = Path("/sys/fs/cgroup")
project = root / "dianzi-r01-20261014"
cache = Path("/tmp/dianzi-docker-static-r01-20261014")
assert os.getuid() == 0 and project.resolve() == project
assert any(line.split()[1:3] == [str(root), "cgroup2"] for line in Path("/proc/mounts").read_text().splitlines())
created_project = not project.exists()
if created_project:
    project.mkdir()
assert project.is_dir() and not (project / "cgroup.procs").read_text().strip()
assert not any(child.is_dir() for child in project.iterdir())
original = (root / "cgroup.subtree_control").read_text().strip()
assert original == "", "Authorization assumes the root delegation is still empty."
controllers = set((root / "cgroup.controllers").read_text().split())
assert {"memory", "cpu", "pids"} <= controllers
fields = ("memory.max", "memory.swap.max", "cpu.max", "pids.max")
directories = [root] + [child for child in root.iterdir() if child.is_dir() and child != project]
before_limits = {str(directory): {name: (directory / name).read_text().strip()
                                  if (directory / name).exists() else None for name in fields}
                 for directory in directories}
record = {"started_at": datetime.now().astimezone().isoformat(timespec="seconds"),
          "parent": str(root), "project": str(project), "original_subtree_control": original,
          "project_created_in_this_call": created_project,
          "project_pids_before": [], "limits_before": before_limits,
          "requested_change": "+memory +cpu +pids",
          "rollback": "After project stops and no other child depends on these controllers, write -memory -cpu -pids to /sys/fs/cgroup/cgroup.subtree_control. Never revoke while another child uses them."}
(cache / "delegation-before.json").write_text(json.dumps(record, indent=2))
(root / "cgroup.subtree_control").write_text("+memory +cpu +pids")
after_limits = {str(directory): {name: (directory / name).read_text().strip()
                                 if (directory / name).exists() else None for name in fields}
                for directory in directories}
for directory, limits in before_limits.items():
    for name, previous in limits.items():
        current = after_limits[directory][name]
        assert previous == current or (previous is None and current in (None, "max", "max 100000")), "Existing limit changed."
assert {"memory", "cpu", "pids"} <= set((project / "cgroup.controllers").read_text().split())
assert all((project / name).exists() for name in fields)
record.update(ended_at=datetime.now().astimezone().isoformat(timespec="seconds"),
              subtree_control_after=(root / "cgroup.subtree_control").read_text().strip(),
              limits_after=after_limits, existing_limits_changed=False)
(cache / "delegation-after.json").write_text(json.dumps(record, indent=2))
failed_runtime = cache / "runtime"
backup_runtime = cache / "runtime-failed-cgroup-20261014T214009"
assert not backup_runtime.exists() and not (failed_runtime / "lifecycle.json").exists()
assert not (failed_runtime / "dockerd.pid").exists()
assert not list((failed_runtime / "data").iterdir()) and not list((failed_runtime / "exec").iterdir())
assert failed_runtime.resolve() == failed_runtime and failed_runtime.parent == cache
failed_runtime.rename(backup_runtime)
record["failed_runtime_preserved_at"] = str(backup_runtime)
print(json.dumps(record, indent=2))
