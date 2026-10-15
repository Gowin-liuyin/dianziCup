"""Confirm Windows can read restored loopback services while the stopped root API stays stopped."""

import json
import socket
import urllib.request
from datetime import datetime

required_ports = (
    25432,
    26379,
    29200,
    25434,
    26381,
    25435,
    26382,
    25436,
    26383,
    29201,
    28201,
    25201,
)
results = {}
for port in required_ports:
    with socket.socket() as connection:
        connection.settimeout(2)
        results[str(port)] = connection.connect_ex(("127.0.0.1", port)) == 0
assert all(results.values())
with socket.socket() as connection:
    connection.settimeout(2)
    root_api_running = connection.connect_ex(("127.0.0.1", 28000)) == 0
assert not root_api_running
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
with opener.open("http://127.0.0.1:28201/v1/health/ready", timeout=5) as response:
    assert response.status == 200 and json.load(response)["status"] == "ready"
with opener.open("http://127.0.0.1:25201/", timeout=5) as response:
    assert response.status == 200
print(
    json.dumps(
        {
            "at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "windows_loopback_tcp": results,
            "root_api_28000_still_stopped": not root_api_running,
            "infra_api_ready": True,
            "infra_frontend_http": 200,
        }
    )
)
