"""Check fixed kernel birth identities without sending signals before requesting owned shutdown."""

from __future__ import annotations

import argparse
import ctypes
import json
import subprocess
import sys
from ctypes import wintypes

from configuration import CORE, OPS, TOTAL_SECONDS, require_activation


def positive_identity(value: object) -> int:
    if type(value) is not int or value <= 0:
        raise ValueError("positive integer process identity required")
    return value


def receipt_ticks(value: object) -> int:
    from windows_actor import _snapshot_ticks

    if not isinstance(value, str):
        raise ValueError("aware receipt timestamp required")
    return _snapshot_ticks(value)


def check_live_birth(
    kernel: ctypes.WinDLL,
    tree: dict[int, dict[str, object]],
    pid: int,
    expected_ticks: int | None = None,
    parent_pid: int | None = None,
    minimum_birth: int | None = None,
) -> int:
    """Use one read-only handle for birth and exit checks, closing only that owned handle."""
    from windows_actor import _creation_ticks

    row = tree.get(pid)
    if row is None or (parent_pid is not None and row.get("parent") != parent_pid):
        raise ValueError("fixed process launcher ancestry differs")
    handle = kernel.OpenProcess(0x100000 | 0x1000, False, pid)
    if not handle:
        raise OSError("fixed process read-only handle unavailable")
    try:
        ticks = _creation_ticks(kernel, handle)
        if expected_ticks is not None and ticks != expected_ticks:
            raise ValueError("fixed kernel creation identity differs")
        if ticks // 10 != receipt_ticks(row.get("created")) // 10:
            raise ValueError("process snapshot generation differs")
        if minimum_birth is not None and ticks < minimum_birth:
            raise ValueError("fixed parent or launcher generation differs")
        if kernel.WaitForSingleObject(handle, 0) != 258:
            raise RuntimeError("fixed process is exited or kernel wait is unknown")
        return ticks
    finally:
        if not kernel.CloseHandle(handle):
            raise OSError("owned read-only handle close failed")


def validate_start_receipts(
    activation: dict[str, object],
    binding: dict[str, object],
    start: dict[str, object],
    guardian: dict[str, object],
) -> tuple[int, int, int, int]:
    from run_binding import object_value

    for key in ("run_id", "nonce"):
        if guardian.get(key) != activation.get(key):
            raise ValueError("new guardian generation differs")
    for key in (
        "product_sha",
        "tool_sha",
        "core_source_sha",
        "operations_source_sha",
        "original_observer_scripts_sha",
        "source_job_ledger_offset",
    ):
        if type(start.get(key)) is not type(binding.get(key)) or start.get(key) != binding.get(key):
            raise ValueError("runtime start binding differs: " + key)
    for key, expected in (
        ("source_job_cap", 450),
        ("prestop", 410),
        ("wire_https_upper_bound", 35100),
    ):
        if type(start.get(key)) is not int or start.get(key) != expected:
            raise ValueError("runtime start budget differs")
    if (
        type(guardian.get("maximum_seconds")) is not int
        or guardian["maximum_seconds"] != TOTAL_SECONDS
    ):
        raise ValueError("guardian total budget differs")
    if not (
        receipt_ticks(guardian.get("started_at"))
        <= receipt_ticks(start.get("started_at"))
        < receipt_ticks(start.get("hard_deadline"))
        <= receipt_ticks(guardian.get("hard_deadline"))
    ):
        raise ValueError("runtime start or deadline generation differs")
    source = object_value(guardian["actual_source_identity"])
    for key in ("run_id", "nonce"):
        if source.get(key) != activation.get(key):
            raise ValueError("actual source receipt generation differs")
    supervisor = positive_identity(start["supervisor_pid"])
    if supervisor != positive_identity(source["actual_pid"]):
        raise ValueError("supervisor differs from guardian source identity")
    return (
        supervisor,
        positive_identity(source["creation_ticks"]),
        positive_identity(guardian["launcher_pid"]),
        positive_identity(guardian["guardian_pid"]),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--capture", action="store_true")
    arguments = parser.parse_args()
    activation = require_activation()
    sys.path.insert(0, str(CORE))
    from authorization import verify_live_authorization
    from run_binding import object_value, read_object
    from windows_actor import process_tree

    binding = verify_live_authorization()
    start = read_object((CORE / "runtime_start.json").read_bytes())
    guardian = read_object((OPS / "guardian_start.json").read_bytes())
    supervisor, source_ticks, source_launcher, guardian_pid = validate_start_receipts(
        activation, binding, start, guardian
    )
    if (CORE / "runtime_end.json").exists():
        raise RuntimeError("fixed runtime already ended")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    tree = process_tree()
    guardian_ticks = check_live_birth(kernel, tree, guardian_pid)
    launcher_ticks = check_live_birth(
        kernel, tree, source_launcher, parent_pid=guardian_pid, minimum_birth=guardian_ticks
    )
    check_live_birth(kernel, tree, supervisor, source_ticks, source_launcher, launcher_ticks)
    started_ticks = receipt_ticks(start["started_at"])
    launchers = object_value(start["launchers"])
    actual_actors = object_value(start["actual_actors"])
    launcher_ids = {
        role: positive_identity(launchers[role]) for role in ("worker", "beat", "api", "observer")
    }
    if len(set(launcher_ids.values())) != 4:
        raise ValueError("fixed actor launchers are ambiguous")
    process_names_raw = json.loads(
        subprocess.check_output(
            [
                "powershell.exe",
                "-NoProfile",
                "-Command",
                "Get-CimInstance Win32_Process | ForEach-Object { "
                "[ordered]@{pid=$_.ProcessId;name=$_.Name} } | ConvertTo-Json -Compress",
            ],
            text=True,
            timeout=3,
        )
    )
    if not isinstance(process_names_raw, list):
        raise ValueError("fixed process snapshot list required")
    process_names: dict[int, str] = {}
    for value in process_names_raw:
        row = object_value(value)
        name = row.get("name")
        if not isinstance(name, str):
            raise ValueError("fixed process snapshot name required")
        snapshot_pid = row.get("pid")
        if type(snapshot_pid) is not int or snapshot_pid < 0:
            raise ValueError("process snapshot PID required")
        process_names[snapshot_pid] = name
    identities: dict[str, dict[str, int]] = {
        "supervisor": {
            "actual_pid": supervisor,
            "creation_ticks": source_ticks,
            "launcher_pid": source_launcher,
        }
    }
    for role in ("worker", "beat", "api", "observer"):
        launcher = launcher_ids[role]
        ticks = check_live_birth(
            kernel,
            tree,
            launcher,
            parent_pid=supervisor,
            minimum_birth=max(source_ticks, started_ticks),
        )
        if role in ("worker", "beat"):
            receipt = object_value(actual_actors[role])
            if receipt.get("role") != role:
                raise ValueError("fixed actor receipt role differs")
            pid = positive_identity(receipt["actual_pid"])
            expected_ticks = positive_identity(receipt["creation_ticks"])
        else:
            children = [
                pid
                for pid, row in tree.items()
                if row.get("parent") == launcher and process_names.get(pid) == "python.exe"
            ]
            if len(children) != 1:
                raise ValueError("fixed actual interpreter is ambiguous")
            pid, expected_ticks = children[0], None
        if pid == launcher:
            raise ValueError("actual interpreter must be the launcher child")
        birth = check_live_birth(kernel, tree, pid, expected_ticks, launcher, ticks)
        identities[role] = {"actual_pid": pid, "creation_ticks": birth, "launcher_pid": launcher}
    if len({row["actual_pid"] for row in identities.values()}) != 5:
        raise ValueError("fixed actor identities are ambiguous")
    capture: dict[str, object] = {
        "identities": identities,
        "runtime_started_at": start["started_at"],
        "deadline": start["hard_deadline"],
        "product_sha": start["product_sha"],
        "tool_sha": start["tool_sha"],
        "signals_sent": 0,
    }
    if arguments.capture:
        with (OPS / "process_ownership_receipt.json").open("xb") as output:
            output.write((json.dumps(capture, indent=2) + "\n").encode())
    else:
        expected = read_object((OPS / "process_ownership_receipt.json").read_bytes())
        expected_identities = object_value(expected["identities"])
        if set(expected_identities) != set(identities):
            raise ValueError("captured actor roles differ")
        for role in identities:
            row = object_value(expected_identities[role])
            if set(row) != {"actual_pid", "creation_ticks", "launcher_pid"}:
                raise ValueError("captured actor identity fields differ")
            if {key: positive_identity(value) for key, value in row.items()} != identities[role]:
                raise ValueError("captured kernel identity differs")
        for key in ("runtime_started_at", "deadline", "product_sha", "tool_sha"):
            if expected.get(key) != capture[key]:
                raise ValueError("captured runtime generation differs")
        if type(expected.get("signals_sent")) is not int or expected["signals_sent"] != 0:
            raise ValueError("captured receipt signal contract differs")
    if not arguments.check and not arguments.capture:
        path = CORE / "stop.request"
        if not path.exists():
            with path.open("xb") as output:
                output.write(
                    b"owned supervisor identity checked; finite beat/worker/observer shutdown\n"
                )
    print(
        json.dumps(
            {
                "operation": "identity_captured"
                if arguments.capture
                else "identity_checked"
                if arguments.check
                else "owned_stop_requested",
                "identities": identities,
                "signals_sent": 0,
            }
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(json.dumps({"error_type": type(error).__name__, "details": "withheld"}))
        raise SystemExit(1) from None
