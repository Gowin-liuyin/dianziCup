"""Run independent schema probes without allowing network or PG connections."""

import json
from pathlib import Path
import socket
import sys

import pytest


RUN = Path(__file__).resolve().parent
label = sys.argv[1] if len(sys.argv) > 1 else "independent_initial"
proposal = len(sys.argv) > 2 and sys.argv[2] == "proposal_only"
attempts: list[str] = []


def deny_connection(connection: socket.socket, address: object) -> None:
    attempts.append(str(address))
    raise AssertionError("This review does not permit network connections")


socket.socket.connect = deny_connection


class ProposedPattern:
    """Only replace the new polling pattern in the in-memory hypothesis run."""

    def pytest_collection_modifyitems(self, items: list[object]) -> None:
        for item in items:
            schema = item.function.__globals__.get("SCHEMA")
            if schema:
                schema["$defs"]["TaskDescriptor"]["properties"]["poll_uri"]["pattern"] = (
                    "^/api/v1/tasks/[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-"
                    "[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
                )


status = pytest.main([
    str(RUN / "test_independent_contract.py"), "-v", "--no-cov", "-p", "no:cacheprovider",
    "--junitxml=" + str(RUN / f"{label}.junit.xml"),
], plugins=[ProposedPattern()] if proposal else [])
(RUN / f"{label}.network.json").write_text(
    json.dumps({"connection_attempts": attempts, "physical_pg_requests": 0,
                "paid_calls": 0, "proposal_only": proposal}, indent=2) + "\n", encoding="utf-8"
)
raise SystemExit(status)
