"""Observe all captured guest control ancestors plus the birth-verified complete tool subtree."""

import json
from pathlib import Path

PROC = Path(r"\\wsl.localhost\Ubuntu-22.04\proc")


def observe(run):
    marker = run / "cbm_resource_control.json"
    if not marker.exists():
        return {}, {"state": "awaiting_control_marker"}
    control = json.loads(marker.read_text())
    entries = {}
    for path in PROC.iterdir():
        if not path.name.isdigit():
            continue
        try:
            raw = (path / "stat").read_text()
            fields = raw.rsplit(")", 1)[1].split()
            pid = int(path.name)
            entries[pid] = {
                "pid": pid, "ppid": int(fields[1]), "birth_clock_ticks": int(fields[19]),
                "comm": raw.split("(", 1)[1].rsplit(")", 1)[0],
            }
        except (OSError, ValueError):
            continue
    root = control["ancestors"][0]
    actual = entries.get(root["pid"])
    if actual is None or actual["birth_clock_ticks"] != root["birth_clock_ticks"]:
        return {}, {"state": "root_exited_or_reused"}
    tool_ids = {root["pid"]}
    while True:
        added = {
            pid for pid, item in entries.items()
            if item["ppid"] in tool_ids
            and item["birth_clock_ticks"] >= entries[item["ppid"]]["birth_clock_ticks"]
        }
        if added <= tool_ids:
            break
        tool_ids.update(added)
    observed = {pid: {**entries[pid], "role": "tool_subtree"} for pid in tool_ids}
    missing = []
    for ancestor in control["ancestors"][1:]:
        item = entries.get(ancestor["pid"])
        if item is None or item["birth_clock_ticks"] != ancestor["birth_clock_ticks"]:
            missing.append(ancestor)
        else:
            observed[item["pid"]] = {**item, "role": "guest_control_ancestor"}
    return observed, {
        "state": "captured",
        "complete_to_pid1": control["complete_to_pid1"],
        "all_ancestor_births_matched": not missing,
        "missing_ancestors": missing,
        "tool_subtree_count": len(tool_ids),
        "control_ancestor_count": len(control["ancestors"]) - 1,
        "shared_init_counted_conservatively_not_terminated": True,
    }
