"""Execute one official CBM tool using an isolated source cache and owned process cap."""

import hashlib
import json
import os
import signal
import subprocess
import sys
import time
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path

RUN = Path(__file__).resolve().parent
CACHE = "/tmp/dianzi-cbm-r12-pfb-cache-20261017"


def identity(pid):
    fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
    return int(fields[1]), int(fields[19])


def descendants(root):
    rows = {}
    for directory in Path("/proc").iterdir():
        if directory.name.isdigit():
            with suppress(FileNotFoundError, ProcessLookupError):
                rows[int(directory.name)] = identity(int(directory.name))
    owned = {root}
    while True:
        added = {pid for pid, (parent, _) in rows.items() if parent in owned} - owned
        if not added:
            return {pid: rows[pid][1] for pid in owned if pid in rows}
        owned.update(added)


def main():
    label, *arguments = sys.argv[1:]
    binary = "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp"
    command = [binary, "cli", "--json", *arguments]
    if label == "binary_help":
        command = [binary, "--help"]
    started = datetime.now(UTC).isoformat()
    with (RUN / (label + ".cbm.log")).open("w") as log:
        process = subprocess.Popen(
            command,
            env=dict(os.environ, CBM_CACHE_DIR=CACHE),
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        owner = {"pid": process.pid, "birth_ticks": identity(process.pid)[1]}
        deadline = time.monotonic() + 54
        peak = len(descendants(os.getpid()))
        stopped = None
        while process.poll() is None:
            peak = max(peak, len(descendants(os.getpid())))
            if peak > 6 or time.monotonic() >= deadline:
                assert identity(process.pid)[1] == owner["birth_ticks"]
                stopped = "process_cap" if peak > 6 else "wall_cap"
                os.killpg(process.pid, signal.SIGKILL)
                break
            time.sleep(0.05)
        code = process.wait(timeout=2)
    remaining = descendants(os.getpid())
    remaining.pop(os.getpid(), None)
    receipt = {
        "argv": command,
        "started_at": started,
        "finished_at": datetime.now(UTC).isoformat(),
        "exit_code": code,
        "wsl_root": owner,
        "binary_sha256": hashlib.sha256(Path(binary).read_bytes()).hexdigest(),
        "wsl_process_peak": peak,
        "wsl_cap": 6,
        "wall_cap_seconds": 54,
        "stopped": stopped,
        "remaining_descendants": remaining,
        "cache": CACHE,
        "log_sha256": hashlib.sha256((RUN / (label + ".cbm.log")).read_bytes()).hexdigest(),
    }
    (RUN / (label + ".cbm.json")).write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
