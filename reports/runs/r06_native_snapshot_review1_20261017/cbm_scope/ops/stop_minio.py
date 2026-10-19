"""Check the new MinIO generation's boot, nonce and kernel identities before its stop request."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from minio_segment import OPS, group_for_nonce, identity


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    start = json.loads((OPS / "minio_start.json").read_bytes())
    prepared = json.loads((OPS / "prepared.json").read_bytes())
    if start["nonce"] != prepared["nonce"]:
        raise ValueError("MinIO generation nonce differs")
    if Path("/proc/sys/kernel/random/boot_id").read_text().strip() != start["boot_id"]:
        raise ValueError("MinIO boot identity changed")
    group = group_for_nonce(start["nonce"])
    if str(group) != start["cgroup"] or group.resolve() != group:
        raise ValueError("new owned MinIO group differs")
    if (OPS / "minio_end.json").exists():
        raise ValueError("new MinIO generation already stopped")
    for role in ("supervisor", "child"):
        expected = start[role]
        if identity(expected["pid"]) != expected:
            raise ValueError("new owned MinIO kernel identity differs")
    if set(group.joinpath("cgroup.procs").read_text().split()) != {
        str(start[role]["pid"]) for role in ("supervisor", "child")
    }:
        raise ValueError("new MinIO group contains unknown process")
    if not arguments.check:
        with (OPS / "minio_stop.request").open("x", encoding="utf-8") as output:
            output.write("owned nonce boot and kernel identities checked\n")
    print(
        json.dumps(
            {
                "operation": "minio_identity_checked"
                if arguments.check
                else "minio_stop_requested",
                "nonce": start["nonce"],
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
