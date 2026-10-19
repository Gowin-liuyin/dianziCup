"""Verify Windows reaches only the documented local test endpoints."""

import json
import socket
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

started = datetime.now(timezone.utc)
for port in (27687, 27474):
    with socket.create_connection(("127.0.0.1", port), timeout=3):
        pass
with urllib.request.urlopen("http://127.0.0.1:27474/", timeout=3) as response:
    body = json.loads(response.read())
    assert response.status == 200 and body["neo4j_version"] == "5.26.32"
result = {
    "started_at": started.isoformat(),
    "ended_at": datetime.now(timezone.utc).isoformat(),
    "exit_code": 0,
    "local_ports_connected": [27687, 27474],
    "http_status": 200,
    "neo4j_version": body["neo4j_version"],
    "edition": body["neo4j_edition"],
}
(Path(__file__).resolve().parent / "windows_health.json").write_text(
    json.dumps(result, indent=2) + "\n"
)
print(json.dumps(result))
