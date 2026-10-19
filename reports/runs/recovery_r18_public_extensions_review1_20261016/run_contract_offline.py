"""Re-run the original contract cases with network connections explicitly denied."""

from __future__ import annotations

import json
from pathlib import Path
import socket
import pytest


RUN = Path(__file__).resolve().parent
attempts: list[str] = []


def deny_connection(connection: socket.socket, address: object) -> None:
    attempts.append(str(address))
    raise AssertionError("This schema review does not permit any network connection")


socket.socket.connect = deny_connection
status = pytest.main([
    "tests/contract/test_r18_public_extensions.py", "-v", "--no-cov",
    "-p", "no:cacheprovider", "--junitxml=" + str(RUN / "original23.junit.xml"),
])
(RUN / "original23.network.json").write_text(
    json.dumps({"connection_attempts": attempts, "physical_pg_requests": 0,
                "paid_calls": 0}, indent=2) + "\n", encoding="utf-8"
)
raise SystemExit(status)
