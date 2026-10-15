"""One bounded public fixed tree GET to verify the actual source shape; no retries."""

import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from ai_intel.infrastructure.network import NetworkPolicy, create_network_gateway

run = Path(__file__).resolve().parent
started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
gateway = create_network_gateway(NetworkPolicy(
    allowed_domains=("api.github.com",), allowed_content_types=("application/json",),
    max_response_bytes=5 * 1024 * 1024, total_timeout_seconds=12,
    dns_resolver="cloudflare_doh",
), max_concurrent_requests=1)
result = gateway.fetch("https://api.github.com/repos/avidml/avid-db/git/trees/main?recursive=1", max_redirect_hops=0)
(run / "avid_tree_public.body").write_bytes(result.body)
payload = json.loads(result.body)
entries = payload.get("tree", [])
records = [entry for entry in entries if isinstance(entry, dict) and isinstance(entry.get("path"), str) and entry["path"].endswith(".json")]
receipt = {
    "started_at": started,
    "ended_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
    "status": result.status_code, "bytes": len(result.body),
    "sha256": hashlib.sha256(result.body).hexdigest(),
    "root_sha": payload.get("sha"), "truncated": payload.get("truncated"),
    "tree_count": len(entries), "json_record_count": len(records),
    "sample_paths": [entry["path"] for entry in records[:8]],
    "headers": dict(result.redacted_headers),
    "scope": "source schema discovery only; not product worker/PG/UI live",
}
(run / "avid_tree_probe.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
print(json.dumps(receipt))
