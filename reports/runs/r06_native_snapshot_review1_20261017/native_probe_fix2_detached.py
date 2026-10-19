"""Root-approved sequential harmless children check native generation and exit boundaries."""

from __future__ import annotations

import ctypes
import json
import ntpath
import os
import subprocess
import sys
import time
from ctypes import wintypes
from datetime import datetime, timedelta, timezone
from pathlib import Path

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
CORE = ROOT / "reports/runs/recovery_r06_activation_prep_20261016/candidate/core"
sys.path[:0] = [str(CORE), str(CORE.parent / "ops")]
from runtime_limits import CpuRate, ExtendedLimits, OwnedJob
from stop_owned import check_live_birth
from windows_actor import (
    OwnershipError,
    WindowsOwnedActor,
    _creation_ticks,
    _snapshot_ticks,
    process_tree,
)


def main() -> None:
    clock = time.monotonic()
    result_path = RUN / "native_fix2_original7_detached.json"
    if result_path.exists():
        raise RuntimeError("native evidence already exists")
    job = OwnedJob()
    kernel = job.kernel
    kernel.GetActiveProcessorCount.argtypes = [wintypes.WORD]
    kernel.GetActiveProcessorCount.restype = wintypes.DWORD
    cpus = kernel.GetActiveProcessorCount(0xFFFF)
    limits = job.query(9, ExtendedLimits)
    limits.basic.active_limit = 10
    limits.basic.flags |= 0x8
    limits.job_memory = 1024**3
    rate = CpuRate(5, min(10000, 20000 // cpus))
    for kind, value in ((9, limits), (15, rate)):
        assert kernel.SetInformationJobObject(
            job.handle, kind, ctypes.byref(value), ctypes.sizeof(value)
        )
    kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [
        ctypes.POINTER(wintypes.FILETIME)
    ] * 4
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    records = []
    failures = []
    identities = []

    def record(name, operation):
        started = datetime.now(timezone(timedelta(hours=8))).isoformat()
        begin = time.monotonic()
        try:
            details = operation()
            status = "passed"
        except (
            OwnershipError,
            ValueError,
            TypeError,
            KeyError,
            AssertionError,
            OSError,
            subprocess.TimeoutExpired,
        ) as error:
            details = {"error_type": type(error).__name__, "message": str(error)}
            failures.append(name)
            status = "failed"
        records.append(
            {
                "name": name,
                "started_at": started,
                "wall_seconds": time.monotonic() - begin,
                "status": status,
                "details": details,
            }
        )
        result_path.write_text(
            json.dumps(
                {"records": records, "identities": identities, "failures": failures},
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    child = subprocess.Popen(
        [sys.executable, "-I", "-B", "-c", "import time; time.sleep(12)"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=0x00000008,
    )
    birth = _creation_ticks(kernel, int(child._handle))
    identities.append(
        {"pid": child.pid, "parent": os.getpid(), "creation_ticks": birth}
    )
    foreign = kernel.CreateJobObjectW(None, None)
    assert foreign

    def refuse(expected, supplied_birth, parent, owned_job):
        try:
            actor = WindowsOwnedActor(child.pid, supplied_birth, parent, owned_job)
        except OwnershipError as error:
            assert expected in str(error)
            assert child.poll() is None
            return {"refusal": str(error), "dummy_alive": True, "signals_sent": 0}
        actor.close()
        raise AssertionError("invalid identity was accepted")

    actor = None
    try:
        record(
            "wrong_birth",
            lambda: refuse("creation changed", birth + 1, os.getpid(), job.handle),
        )
        record(
            "foreign_job",
            lambda: refuse("outside owned Job", birth, os.getpid(), foreign),
        )
        record(
            "wrong_ancestry",
            lambda: refuse(
                "not the owned launcher child", birth, os.getppid(), job.handle
            ),
        )

        def accept_parent():
            nonlocal actor
            actor = WindowsOwnedActor(child.pid, birth, os.getpid(), job.handle)
            assert not actor.exited()
            tree = process_tree()
            assert tree[child.pid]["parent"] == os.getpid()
            assert _snapshot_ticks(str(tree[child.pid]["created"])) // 10 == birth // 10
            return {
                "actual_pid": child.pid,
                "creation_ticks": birth,
                "owned_parent": os.getpid(),
                "snapshot_rows": len(tree),
            }

        record("correct_parent", accept_parent)

        def stop_name_and_birth():
            tree = process_tree()
            names = {pid: row["name"] for pid, row in tree.items()}
            selected = [
                pid
                for pid, row in tree.items()
                if row["parent"] == os.getpid()
                and names[pid] == ntpath.basename(sys.executable)
            ]
            assert selected == [child.pid]
            assert (
                check_live_birth(kernel, tree, child.pid, birth, os.getpid()) == birth
            )
            return {
                "actual_name": names[child.pid],
                "selected_pid": selected,
                "signals_sent": 0,
            }

        record("stop_names_and_read_only_birth", stop_name_and_birth)
        if actor is not None:

            def terminate_owned():
                actor.kill_owned_tree()
                assert child.wait(timeout=1) == 70
                assert actor.exited()
                return {"exit_code": child.returncode, "held_ack": True}

            record("owned_tree_shutdown", terminate_owned)
    finally:
        if actor is not None:
            actor.close()
        kernel.CloseHandle(foreign)
        if child.poll() is None:
            assert _creation_ticks(kernel, int(child._handle)) == birth
            membership = wintypes.BOOL()
            kernel.IsProcessInJob.argtypes = [
                wintypes.HANDLE,
                wintypes.HANDLE,
                ctypes.POINTER(wintypes.BOOL),
            ]
            assert (
                kernel.IsProcessInJob(
                    int(child._handle), job.handle, ctypes.byref(membership)
                )
                and membership.value
            )
            child.kill()
        child.wait(timeout=1)
        assert kernel.WaitForSingleObject(int(child._handle), 0) == 0
        identities[0].update(exit_code=child.returncode, held_exit_ack=True)

    def real_exit():
        exited = subprocess.Popen(
            [sys.executable, "-I", "-B", "-c", "raise SystemExit(23)"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=0x00000008,
        )
        ticks = _creation_ticks(kernel, int(exited._handle))
        try:
            assert exited.wait(timeout=1) == 23
            assert kernel.WaitForSingleObject(int(exited._handle), 0) == 0
            assert _creation_ticks(kernel, int(exited._handle)) == ticks
            tree = process_tree()
            assert exited.pid not in tree
            try:
                check_live_birth(kernel, tree, exited.pid, ticks, os.getpid())
            except ValueError:
                pass
            else:
                raise AssertionError("exited process accepted")
            identities.append(
                {
                    "pid": exited.pid,
                    "parent": os.getpid(),
                    "creation_ticks": ticks,
                    "exit_code": 23,
                    "held_exit_ack": True,
                }
            )
            return {
                "pid": exited.pid,
                "creation_ticks": ticks,
                "exit_code": 23,
                "held_ack": True,
                "absent_from_snapshot": True,
                "stop_refused": True,
            }
        finally:
            if exited.poll() is None:
                exited.kill()
                exited.wait(timeout=1)

    record("real_exit23_and_exited_stop_refusal", real_exit)
    summary = {
        "records": records,
        "identities": identities,
        "failures": failures,
        "wall_seconds": time.monotonic() - clock,
        "job_usage_after": job.usage(),
        "source_pg_minio_wsl_started": False,
        "paid_requests": 0,
    }
    result_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "cases": len(records),
                "failures": failures,
                "wall_seconds": summary["wall_seconds"],
            }
        )
    )
    return bool(failures)


if __name__ == "__main__":
    main()
