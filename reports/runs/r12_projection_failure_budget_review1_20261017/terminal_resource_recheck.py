"""Confirm all short guest relay and tool identities have exited while preserving shared init."""

import json
from datetime import UTC, datetime
from pathlib import Path

import batch13_process_metadata as metadata

RUN = Path(__file__).parent
PROC = Path(r"\\wsl.localhost\Ubuntu-22.04\proc")
control = json.loads((RUN / "cbm_resource_control.json").read_text())
results = json.loads((RUN / "cbm_resource_results.json").read_text())
identities = control["ancestors"] + [item["child_identity"] for item in results["results"]]
observations = []
for original in identities:
    pid = original["pid"]
    try:
        raw = (PROC / str(pid) / "stat").read_text()
        actual = int(raw.rsplit(")", 1)[1].split()[19])
        state = "same_birth_active" if actual == original["birth_clock_ticks"] else "pid_reused"
    except FileNotFoundError:
        state = "exited"
    except OSError:
        state = "identity_unavailable"
    observations.append({
        **original, "state": state,
        "scope": "shared_init_ancestor" if pid == 1 else "temporary_control_or_tool",
    })
temporary = [item for item in observations if item["pid"] != 1]
unresolved = [item for item in temporary if item["state"] not in {"exited", "pid_reused"}]
receipt = json.loads((RUN / "cbm_resource_recheck.command.json").read_text())
windows = []
for item in receipt["windows_peak_chain"]:
    try:
        actual = metadata.identity(item["pid"])
        state = "same_birth_active" if actual["birth_utc"] == item["birth_utc"] else "pid_reused"
    except OSError:
        state = "exited_or_identity_unavailable"
    windows.append({**item, "state": state})
record = {
    "checked_at": datetime.now(UTC).isoformat(),
    "guest_identity_observations": observations,
    "windows_identity_observations": windows,
    "temporary_guest_unresolved": unresolved,
    "temporary_guest_count": len(temporary),
    "shared_init_expected_active": True,
    "shared_init_never_terminated": True,
    "complete_control_coverage": receipt["linux_control_coverage"],
}
(RUN / "terminal_resource_boundary.json").write_text(json.dumps(record, indent=2) + "\n")
assert not unresolved
assert not any(item["state"] == "same_birth_active" for item in windows)
print(json.dumps({"temporary_guest_count": len(temporary), "temporary_guest_unresolved": len(unresolved)}))
