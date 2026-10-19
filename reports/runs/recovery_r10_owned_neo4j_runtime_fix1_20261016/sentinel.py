"""Write, recover and remove only the explicitly owned graceful-recovery sentinel."""

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from neo4j import GraphDatabase, Query

OUTPUT = Path(__file__).resolve().parent
PWSH = "C:/Users/yinha/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/powershell/pwsh.exe"
parser = argparse.ArgumentParser()
parser.add_argument("operation", choices=("create", "verify_delete"))
operation = parser.parse_args().operation
unlock = "$ErrorActionPreference='Stop'; $secure=ConvertTo-SecureString ([IO.File]::ReadAllText('D:/dianzi-private/r10-neo4j-test-20261016.dpapi')); $pointer=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure); try { [Console]::Write([Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)) } finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer) }"
started = datetime.now(timezone.utc)
result = subprocess.run(
    [PWSH, "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", unlock],
    capture_output=True,
    text=True,
    timeout=25,
    check=False,
)
assert result.returncode == 0, "DPAPI unprotect failed"
secret = json.loads(result.stdout)
resource = json.loads((OUTPUT / "resource_started.json").read_text())
assert (
    secret["resource_id"] == resource["resource_id"] == "dianzi-r10-neo4j-test-20261016"
)
assert secret["deadline"] == resource["deadline"] == "2026-10-16T19:35:43.312788+08:00"
assert datetime.now(timezone.utc) < datetime.fromisoformat(secret["deadline"])
assert (
    secret["NEO4J_TEST_BOLT_URL"] == "bolt://127.0.0.1:27687"
    and secret["NEO4J_TEST_USERNAME"] == "neo4j"
)
parameters = {
    "runtime_key": "r10-owned-runtime-fix1-20261016",
    "container_id": resource["container_id"],
    "payload": "owned-graceful-recovery-sentinel",
}
with GraphDatabase.driver(
    secret["NEO4J_TEST_BOLT_URL"],
    auth=(secret["NEO4J_TEST_USERNAME"], secret["NEO4J_TEST_PASSWORD"]),
    connection_timeout=3,
    connection_acquisition_timeout=3,
    max_connection_pool_size=1,
    max_transaction_retry_time=0,
    telemetry_disabled=True,
) as driver:
    driver.verify_connectivity()
    with driver.session(database="neo4j") as session:
        if operation == "create":
            existing = session.run(
                Query(
                    "MATCH (s:R10RuntimeFixSentinel {runtime_key: $runtime_key, container_id: $container_id}) RETURN count(s) AS count",
                    timeout=3,
                ),
                parameters,
            ).single(strict=True)
            assert existing["count"] == 0, "Unknown sentinel must not be overwritten"
            summary = session.run(
                Query(
                    "CREATE (s:R10RuntimeFixSentinel {runtime_key: $runtime_key, container_id: $container_id, payload: $payload}) RETURN s.runtime_key AS runtime_key",
                    timeout=3,
                ),
                parameters,
            ).consume()
            assert summary.counters.nodes_created == 1
        else:
            row = session.run(
                Query(
                    "MATCH (s:R10RuntimeFixSentinel {runtime_key: $runtime_key, container_id: $container_id}) RETURN s.payload AS payload",
                    timeout=3,
                ),
                parameters,
            ).single(strict=True)
            assert row["payload"] == parameters["payload"]
            summary = session.run(
                Query(
                    "MATCH (s:R10RuntimeFixSentinel {runtime_key: $runtime_key, container_id: $container_id, payload: $payload}) DELETE s",
                    timeout=3,
                ),
                parameters,
            ).consume()
            assert summary.counters.nodes_deleted == 1
            remaining = session.run(
                Query(
                    "MATCH (s:R10RuntimeFixSentinel {runtime_key: $runtime_key, container_id: $container_id}) RETURN count(s) AS count",
                    timeout=3,
                ),
                parameters,
            ).single(strict=True)
            assert remaining["count"] == 0
receipt = {
    "started_at": started.isoformat(),
    "ended_at": datetime.now(timezone.utc).isoformat(),
    "operation": operation,
    "exit_code": 0,
    "container_id": resource["container_id"],
    "owned_namespace": "R10RuntimeFixSentinel/runtime_key=r10-owned-runtime-fix1-20261016",
    "payload_match": True,
    "database": "neo4j",
    "deadline": secret["deadline"],
    "business_nodes_modified": 0,
}
(OUTPUT / ("sentinel_" + operation + ".json")).write_text(
    json.dumps(receipt, indent=2) + "\n"
)
print(json.dumps(receipt))
