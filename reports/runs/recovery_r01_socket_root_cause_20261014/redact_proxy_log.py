"""Copy this daemon log while removing any exact inherited proxy values."""

import json
import os
from datetime import datetime
from pathlib import Path


cache = Path("/tmp/dianzi-docker-static-r01-20261014")
destination = Path(__file__).resolve().parent
source = cache / "runtime/dockerd.log"
content = source.read_text()
redactions = 0
for key in ("HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "http_proxy", "https_proxy", "no_proxy"):
    value = os.environ.get(key)
    if value and value in content:
        redactions += content.count(value)
        content = content.replace(value, "[REDACTED_PROXY_VALUE]")
(destination / "portable_dockerd.log").write_text(content)
(destination / "daemon_log_export.json").write_text(json.dumps({
    "recorded_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    "source": str(source), "proxy_value_redactions": redactions,
    "raw_log_preserved_at_source": True, "exported_bytes": len(content.encode())}, indent=2))
