"""Authenticate the owned Neo4j instance and inspect only runtime metadata."""

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import neo4j
from neo4j import GraphDatabase, Query

OUTPUT = Path(__file__).resolve().parent
PWSH = "C:/Users/yinha/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/powershell/pwsh.exe"
unlock = "$ErrorActionPreference='Stop'; $secure=ConvertTo-SecureString ([IO.File]::ReadAllText('D:/dianzi-private/r10-neo4j-test-20261016.dpapi')); $pointer=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure); try { [Console]::Write([Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)) } finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer) }"
started = datetime.now(timezone.utc)
unprotected = subprocess.run(
    [PWSH, "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", unlock],
    capture_output=True,
    text=True,
    timeout=25,
    check=False,
)
assert unprotected.returncode == 0, "Current-user DPAPI unprotect failed"
secret = json.loads(unprotected.stdout)
resource = json.loads((OUTPUT / "resource_started.json").read_text())
assert (
    secret["resource_id"] == resource["resource_id"] == "dianzi-r10-neo4j-test-20261016"
)
assert secret["deadline"] == resource["deadline"]
assert datetime.now(timezone.utc) < datetime.fromisoformat(secret["deadline"])
assert secret["NEO4J_TEST_BOLT_URL"] == "bolt://127.0.0.1:27687"
assert secret["NEO4J_TEST_USERNAME"] == "neo4j" and neo4j.__version__ == "6.4.0"
names = [
    "server.default_listen_address",
    "server.bolt.listen_address",
    "server.http.listen_address",
    "server.https.enabled",
    "dbms.routing.enabled",
    "server.memory.heap.initial_size",
    "server.memory.heap.max_size",
    "server.memory.pagecache.size",
    "db.transaction.timeout",
    "db.lock.acquisition.timeout",
    "dbms.usage_report.enabled",
]
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
    server = driver.get_server_info()
    with driver.session(
        database="neo4j", default_access_mode=neo4j.READ_ACCESS
    ) as session:
        row = session.run(Query("RETURN 1 AS healthy", timeout=3)).single(strict=True)
        assert row["healthy"] == 1
        settings = {
            record["name"]: record["value"]
            for record in session.run(
                Query(
                    "SHOW SETTINGS YIELD name, value WHERE name IN $names RETURN name, value ORDER BY name",
                    timeout=3,
                ),
                names=names,
            )
        }
    assert settings["server.bolt.listen_address"] == "127.0.0.1:27687"
    assert settings["server.http.listen_address"] == "127.0.0.1:27474"
    assert (
        settings["server.https.enabled"] == "false"
        and settings["dbms.routing.enabled"] == "false"
    )
    assert (
        settings["db.transaction.timeout"] == "3s"
        and settings["db.lock.acquisition.timeout"] == "2s"
    )
    assert settings["dbms.usage_report.enabled"] == "false"
result = {
    "started_at": started.isoformat(),
    "ended_at": datetime.now(timezone.utc).isoformat(),
    "exit_code": 0,
    "driver_version": neo4j.__version__,
    "driver_telemetry_disabled": True,
    "server_agent": server.agent,
    "bolt_protocol_version": list(server.protocol_version),
    "resource_id": secret["resource_id"],
    "deadline": secret["deadline"],
    "container_id": resource["container_id"],
    "authentication": "passed",
    "return_one": 1,
    "settings": settings,
    "business_fact_queries": 0,
}
(OUTPUT / "bolt_smoke.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result))
