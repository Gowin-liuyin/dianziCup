"""Recheck frozen contracts without permitting network or schema replacement."""

import json
from pathlib import Path
import socket
import sys

import pytest


RUN = Path(__file__).resolve().parent
suite = sys.argv[1]
attempts: list[str] = []


def deny_connection(connection: socket.socket, address: object) -> None:
    attempts.append(str(address))
    raise AssertionError("The contract recheck does not allow network connections")


socket.socket.connect = deny_connection
paths = (
    ["tests/contract/test_r18_public_extensions.py", "tests/contract/test_r18_task_poll_uri.py"]
    if suite == "original28"
    else [str(RUN / "test_independent_contract.py")]
)
status = pytest.main([
    *paths, "-c", "pyproject.toml", "-v", "--no-cov", "-p", "no:cacheprovider",
    "--junitxml=" + str(RUN / f"{suite}.junit.xml"),
])
(RUN / f"{suite}.network.json").write_text(
    json.dumps({"connection_attempts": attempts, "physical_pg_requests": 0,
                "paid_calls": 0, "schema_loaded_from_frozen_file": True,
                "memory_schema_replacement": False}, indent=2) + "\n", encoding="utf-8"
)
raise SystemExit(status)
