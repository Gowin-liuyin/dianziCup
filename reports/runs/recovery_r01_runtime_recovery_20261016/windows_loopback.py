"""Verify the three restored test endpoints from Windows without reading secrets."""

import json
import socket
import urllib.request
from datetime import datetime
from pathlib import Path

started_at = datetime.now().astimezone().isoformat(timespec="seconds")
for port in (25432, 26379, 29200):
    with socket.create_connection(("127.0.0.1", port), timeout=3):
        pass
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
with opener.open("http://127.0.0.1:29200/_cluster/health", timeout=5) as response:
    assert response.status == 200
    assert json.load(response)["status"] == "green"
receipt = {
    "started_at": started_at,
    "ended_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    "ports_connected": [25432, 26379, 29200],
    "search_health": "green",
    "secret_inputs": False,
}
Path(__file__).with_name("windows_loopback_receipt.json").write_text(
    json.dumps(receipt, indent=2)
)
print(json.dumps(receipt))
