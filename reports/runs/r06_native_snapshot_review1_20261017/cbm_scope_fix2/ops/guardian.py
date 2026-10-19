"""Hold the actual source owner handle and enforce the six-hour plus shutdown hard deadline."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta

from configuration import (
    CORE,
    OPS,
    PARENT_END,
    PRODUCT,
    RUN_ID,
    TOTAL_SECONDS,
    ZONE,
    read_launch_state,
    require_activation,
    require_start_window,
)


def deadline_reached(now: datetime, deadline: datetime, monotonic: float, limit: float) -> bool:
    return now >= deadline or monotonic >= limit


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", action="store_true")
    arguments = parser.parse_args()
    if not arguments.start:
        raise ValueError("explicit root start required")
    activation = require_activation()
    require_start_window(datetime.now(ZONE))
    launch_state = read_launch_state()
    if launch_state["runtime_binding_sha256"] != activation["runtime_binding_sha256"]:
        raise ValueError("guardian launch configuration differs")
    prior_cpu = launch_state["cpu_seconds_used"]
    sys.path.insert(0, str(CORE))
    from runtime_controls import CPU_SECONDS_CAP
    from runtime_limits import OwnedJob
    from windows_actor import WindowsOwnedActor, _creation_ticks

    job = OwnedJob()

    started = datetime.now(ZONE)
    wall_deadline = min(started + timedelta(seconds=TOTAL_SECONDS), PARENT_END)
    monotonic_deadline = time.monotonic() + TOTAL_SECONDS
    forced_stop_by = wall_deadline - timedelta(seconds=15)
    actor = None
    reason = "source_owner_exit"
    with (
        (OPS / "supervisor.stdout.log").open("xb") as stdout,
        (OPS / "supervisor.stderr.log").open("xb") as stderr,
    ):
        process = subprocess.Popen(
            [sys.executable, "-B", str(OPS / "source_entry.py")],
            cwd=PRODUCT / "backend",
            stdout=stdout,
            stderr=stderr,
            creationflags=0x08000000,
        )
        ready_limit = time.monotonic() + 30
        try:
            while not (OPS / "source_identity.json").exists():
                if process.poll() is not None or time.monotonic() >= ready_limit:
                    raise RuntimeError("early actual source identity unavailable")
                time.sleep(0.05)
            identity = json.loads((OPS / "source_identity.json").read_bytes())
            if identity["nonce"] != activation["nonce"] or identity["run_id"] != RUN_ID:
                raise RuntimeError("actual source generation differs")
            actor = WindowsOwnedActor(
                identity["actual_pid"],
                identity["creation_ticks"],
                process.pid,
                job.handle,
            )
            with (OPS / "guardian_start.json").open("x", encoding="utf-8") as output:
                json.dump(
                    {
                        "started_at": started.isoformat(),
                        "hard_deadline": wall_deadline.isoformat(),
                        "forced_stop_by": forced_stop_by.isoformat(),
                        "monotonic_deadline": monotonic_deadline,
                        "run_id": RUN_ID,
                        "nonce": activation["nonce"],
                        "guardian_pid": os.getpid(),
                        "product_sha": activation["product_sha"],
                        "runtime_binding_sha256": activation["runtime_binding_sha256"],
                        "observation_id": launch_state["observation_id"],
                        "launcher_pid": process.pid,
                        "actual_source_identity": identity,
                        "maximum_seconds": TOTAL_SECONDS,
                    },
                    output,
                    indent=2,
                )
                output.write("\n")
            while not actor.exited():
                if prior_cpu + job.usage()["cpu_seconds"] >= CPU_SECONDS_CAP:
                    reason = "guardian_aggregate_cpu_budget"
                    break
                if deadline_reached(
                    datetime.now(ZONE),
                    forced_stop_by,
                    time.monotonic(),
                    monotonic_deadline - 15,
                ):
                    reason = "absolute_shutdown_hard_limit"
                    break
                time.sleep(0.25)
        finally:
            kernel_exit_ack = False
            if actor is not None:
                try:
                    if not actor.exited():
                        if (
                            _creation_ticks(actor.kernel, actor.handle)
                            != identity["creation_ticks"]
                        ):
                            raise RuntimeError("source handle kernel identity changed")
                        if not actor.kernel.TerminateProcess(actor.handle, 70):
                            raise OSError("owned source owner termination failed")
                        if actor.kernel.WaitForSingleObject(actor.handle, 5000) != 0:
                            raise RuntimeError("owned source kernel exit ACK unavailable")
                    kernel_exit_ack = actor.exited()
                finally:
                    actor.close()
            else:
                from ctypes import wintypes

                job.kernel.TerminateJobObject.argtypes = [
                    wintypes.HANDLE,
                    wintypes.UINT,
                ]
                if not job.kernel.TerminateJobObject(job.handle, 70):
                    raise RuntimeError("owned launch group could not fail closed")
            if process.poll() is None:
                process.wait(timeout=5)
            with (OPS / "guardian_end.json").open("x", encoding="utf-8") as output:
                json.dump(
                    {
                        "started_at": started.isoformat(),
                        "ended_at": datetime.now(ZONE).isoformat(),
                        "run_id": RUN_ID,
                        "nonce": activation["nonce"],
                        "reason": reason,
                        "actual_source_kernel_exit_ack": kernel_exit_ack,
                        "product_sha": activation["product_sha"],
                        "runtime_binding_sha256": activation["runtime_binding_sha256"],
                        "observation_id": launch_state["observation_id"],
                        "source_job_kill_on_close_required": True,
                        "descendant_exit_confirmation": "requires_final_actual_kernel_check",
                        "cpu_seconds_used": job.usage()["cpu_seconds"],
                        "formal_six_hour_pass": False,
                    },
                    output,
                    indent=2,
                )
                output.write("\n")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(json.dumps({"error_type": type(error).__name__, "details": "withheld"}))
        raise SystemExit(1) from None
