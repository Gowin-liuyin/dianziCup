"""Reproduce Linux signal permission rules only in owned anonymous children."""

import ctypes
import errno
import json
import os
import signal
from pathlib import Path


class CapabilityHeader(ctypes.Structure):
    _fields_ = [("version", ctypes.c_uint32), ("pid", ctypes.c_int)]


class CapabilityData(ctypes.Structure):
    _fields_ = [
        ("effective", ctypes.c_uint32),
        ("permitted", ctypes.c_uint32),
        ("inheritable", ctypes.c_uint32),
    ]


def set_child_capabilities(mask):
    header = CapabilityHeader(0x20080522, 0)
    capabilities = (CapabilityData * 2)()
    capabilities[0].effective = capabilities[0].permitted = mask
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.capset(ctypes.byref(header), ctypes.byref(capabilities)) != 0:
        raise OSError(ctypes.get_errno(), "capset")


def credentials():
    fields = dict(
        line.split(":", 1)
        for line in Path("/proc/self/status").read_text().splitlines()
        if ":" in line
    )
    return {name: fields[name].strip() for name in ("Uid", "Gid", "CapEff", "CapPrm")}


def case(mask, same_uid):
    read_ready, write_ready = os.pipe()
    target_pid = os.fork()
    if target_pid == 0:
        os.close(read_ready)
        os.setpgid(0, 0)
        os.setgroups([])
        os.setresgid(7474, 7474, 7474)
        os.setresuid(7474, 7474, 7474)
        signal.signal(signal.SIGTERM, lambda number, frame: os._exit(0))
        signal.signal(signal.SIGALRM, lambda number, frame: os._exit(124))
        signal.alarm(5)
        os.write(write_ready, json.dumps(credentials()).encode())
        os.close(write_ready)
        while True:
            signal.pause()
    os.close(write_ready)
    target_credentials = json.loads(os.read(read_ready, 4096))
    os.close(read_ready)
    if same_uid:
        os.setgroups([])
        os.setresgid(7474, 7474, 7474)
        os.setresuid(7474, 7474, 7474)
    set_child_capabilities(mask)
    sender_credentials = credentials()
    try:
        os.killpg(target_pid, signal.SIGTERM)
        signal_errno = 0
    except PermissionError as error:
        signal_errno = error.errno
    if signal_errno:
        assert signal_errno == errno.EPERM
        assert os.waitpid(target_pid, os.WNOHANG) == (0, 0)
        os.setgroups([])
        os.setresgid(7474, 7474, 7474)
        os.setresuid(7474, 7474, 7474)
        os.killpg(target_pid, signal.SIGTERM)
    waited_pid, status = os.waitpid(target_pid, 0)
    assert waited_pid == target_pid and os.waitstatus_to_exitcode(status) == 0
    return {
        "sender": sender_credentials,
        "target": target_credentials,
        "signal": "SIGTERM",
        "target_scope": "isolated_owned_child_process_group",
        "signal_errno": signal_errno,
        "same_uid_cleanup": bool(signal_errno),
        "target_exit": 0,
    }


results = []
for mask, same_uid, expected_errno in (
    (0xCB, False, errno.EPERM),
    (0xEB, False, 0),
    (0, True, 0),
):
    result_reader, result_writer = os.pipe()
    worker_pid = os.fork()
    if worker_pid == 0:
        os.close(result_reader)
        try:
            result = case(mask, same_uid)
            assert result["signal_errno"] == expected_errno
            os.write(result_writer, json.dumps(result).encode())
            os._exit(0)
        except (AssertionError, OSError, ValueError):
            os._exit(1)
    os.close(result_writer)
    payload = os.read(result_reader, 4096)
    os.close(result_reader)
    waited_pid, status = os.waitpid(worker_pid, 0)
    assert waited_pid == worker_pid and os.waitstatus_to_exitcode(status) == 0
    results.append(json.loads(payload))
print(
    json.dumps(
        {
            "fixture_mode": "synthetic_owned_children",
            "cases": results,
            "count": 3,
            "real_service_signals": 0,
            "real_container_capability_changes": 0,
        }
    )
)
