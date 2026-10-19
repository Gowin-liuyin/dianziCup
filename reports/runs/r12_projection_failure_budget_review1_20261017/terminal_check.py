"""Check earlier owned PID birth identities and current Linux tool descendants after exit."""

import json
from datetime import UTC, datetime
from pathlib import Path

import batch13_process_metadata as metadata

RUN = Path(__file__).parent
windows = {}
linux = {}
for path in RUN.glob("*.command.json"):
    receipt = json.loads(path.read_text())
    for item in receipt["windows_peak_chain"]:
        key = (item["pid"], item["birth_utc"])
        windows[key] = item
    for item in receipt.get("linux_peak_chain", []):
        key = (item["pid"], item["birth_clock_ticks"])
        linux[key] = item
windows_results = []
for (pid, birth), item in windows.items():
    try:
        actual = metadata.identity(pid)
        state = "still_active" if actual["birth_utc"] == birth else "pid_reused"
    except OSError:
        state = "exited_or_identity_unavailable"
    windows_results.append({**item, "state": state})
linux_results = []
for (pid, birth), item in linux.items():
    path = Path(r"\\wsl.localhost\Ubuntu-22.04\proc") / str(pid) / "stat"
    try:
        actual = int(path.read_text().rsplit(")", 1)[1].split()[19])
        state = "still_active" if actual == birth else "pid_reused"
    except FileNotFoundError:
        state = "exited"
    except OSError:
        state = "identity_unavailable"
    linux_results.append({**item, "state": state})
result = {
    "checked_at": datetime.now(UTC).isoformat(),
    "windows_observations": windows_results,
    "linux_observations": linux_results,
    "windows_same_birth_active": sum(item["state"] == "still_active" for item in windows_results),
    "linux_same_birth_active": sum(item["state"] == "still_active" for item in linux_results),
    "linux_current_owned_tools": metadata.linux_owned(RUN),
    "linux_proxy_ancestor_birth": "not_captured_in_initial_cbm_window",
}
(RUN / "terminal_boundary.json").write_text(json.dumps(result, indent=2) + "\n")
assert result["windows_same_birth_active"] == result["linux_same_birth_active"] == 0
assert not result["linux_current_owned_tools"]
print(json.dumps({key: result[key] for key in (
    "windows_same_birth_active", "linux_same_birth_active", "linux_current_owned_tools"
)}))
