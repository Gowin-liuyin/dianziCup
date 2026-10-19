"""Stop beat, bounded current worker work, then permit the observer's final PG read."""

from __future__ import annotations

import json
import os
import time
from datetime import UTC, datetime
from typing import Literal

from owned_stop_watcher import ACK_LIMIT_BYTES, owned_control_path, read_stop_request
from runtime_controls import StopObservation, stop_action
from windows_actor import OwnershipError, WindowsOwnedActor


def read_actor_receipt(
    role: Literal["worker", "beat"], kind: Literal["ready", "ack"]
) -> dict[str, object]:
    path = owned_control_path(role, kind)
    if path.is_symlink() or path.is_junction() or path.stat().st_size > ACK_LIMIT_BYTES:
        raise OwnershipError("owned actor receipt is invalid")
    value = json.loads(path.read_bytes())
    if (
        set(value) != {"role", "observed_at", "actual_pid", "creation_ticks"}
        or value["role"] != role
    ):
        raise OwnershipError("owned actor receipt schema differs")
    if type(value["actual_pid"]) is not int or value["actual_pid"] < 1:
        raise OwnershipError("actual actor PID unavailable")
    if type(value["creation_ticks"]) is not int or value["creation_ticks"] < 1:
        raise OwnershipError("actual actor creation unavailable")
    return value


def request_actor_stop(role: Literal["worker", "beat"]) -> None:
    path = owned_control_path(role, "stop")
    payload = json.dumps({"role": role, "owned_stop": True}).encode() + b"\n"
    if path.exists():
        if not read_stop_request(role):
            raise OwnershipError("owned stop request differs")
        return
    pending = path.with_suffix(".pending")
    with pending.open("xb") as output:
        output.write(payload)
        output.flush()
        os.fsync(output.fileno())
    pending.replace(path)


def stop_actor(
    role: Literal["worker", "beat"],
    actor: WindowsOwnedActor,
    ready: dict[str, object],
    lease_expires_at: datetime | None,
    hard_guard: bool,
) -> dict[str, object]:
    request_actor_stop(role)
    started = time.monotonic()
    acknowledgement = None
    action = "wait_ack"
    while True:
        if owned_control_path(role, "ack").exists():
            acknowledgement = read_actor_receipt(role, "ack")
        matches = acknowledgement is None or all(
            acknowledgement[key] == ready[key] for key in ("actual_pid", "creation_ticks")
        )
        observation = StopObservation(
            acknowledgement is not None, matches, actor.exited(), time.monotonic() - started
        )
        action = stop_action(
            role,
            observation,
            datetime.now(UTC),
            lease_expires_at,
            hard_guard or time.monotonic() - started >= 65,
        )
        if action in ("ended_with_ack", "ended_without_ack_failure"):
            break
        if action == "refuse_pid_signal_close_owned_supervisor_job":
            raise OwnershipError("owned actor acknowledgement identity differs")
        if action == "kill_owned_tree":
            actor.kill_owned_tree()
            if not actor.exited():
                raise OwnershipError("owned actor termination not confirmed")
            break
        time.sleep(0.05)
    return {
        "role": role,
        "actual_pid": ready["actual_pid"],
        "creation_ticks": ready["creation_ticks"],
        "ack_present": acknowledgement is not None,
        "actual_pid_exited": actor.exited(),
        "action": action,
        "seconds": time.monotonic() - started,
    }
