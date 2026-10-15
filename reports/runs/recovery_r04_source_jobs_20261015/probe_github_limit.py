"""一次读取不消耗主REST额度的官方配额端点；不重试采集或注入身份。"""

import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from ai_intel.infrastructure.network import NetworkPolicy, create_network_gateway

RUN = Path(__file__).resolve().parent
target = RUN / "github_limit_probe.json"
assert not target.exists()
clock = ZoneInfo("Asia/Shanghai")
started = datetime.now(clock).isoformat(timespec="seconds")
gateway = create_network_gateway(NetworkPolicy(
    allowed_domains=("api.github.com",), dns_resolver="cloudflare_doh",
    allowed_content_types=("application/json",), total_timeout_seconds=12))
response = gateway.fetch("https://api.github.com/rate_limit", max_redirect_hops=0)
payload = json.loads(response.body)
rate = payload.get("rate", {}) if isinstance(payload, dict) else {}
safe_rate = {key: rate[key] for key in ("limit", "used", "remaining", "reset")
             if key in rate and type(rate[key]) is int}
reset = safe_rate.get("reset")
target.write_text(json.dumps({"started_at": started,
    "ended_at": datetime.now(clock).isoformat(timespec="seconds"),
    "http_status": response.status_code, "rate": safe_rate,
    "reset_beijing": datetime.fromtimestamp(reset, clock).isoformat(timespec="seconds") if reset else None,
    "response_sha256": hashlib.sha256(response.body).hexdigest(),
    "source_requests_retried": False, "credentials_used": False}, indent=2))
print(target.read_text())
