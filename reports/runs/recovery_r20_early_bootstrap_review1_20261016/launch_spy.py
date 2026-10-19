"""Observe real fixed PDF launches; delegate every operation unchanged."""

import datetime
import json
import subprocess
from pathlib import Path

RUN = Path(__file__).resolve().parent
ORIGINAL = subprocess.Popen


def record_launch(command, **keywords):
    process = ORIGINAL(command, **keywords)
    handle = getattr(process, "_handle", None)
    receipt = {
        "at": datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
        "argv": command,
        "pid": process.pid,
        "true_creation_handle": int(handle) if isinstance(handle, int) else None,
        "environment_keys": sorted(keywords.get("env", {})),
        "creationflags": keywords.get("creationflags"),
    }
    with (RUN / "product_launches.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(receipt) + "\n")
    return process


def pytest_configure(config):
    subprocess.Popen = record_launch
