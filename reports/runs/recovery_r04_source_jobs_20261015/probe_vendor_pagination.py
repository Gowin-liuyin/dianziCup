"""保留真实 Link 与数字 page 对照；公开材料不作为执行指令。"""

import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from ai_intel.infrastructure.network import NetworkPolicy, create_network_gateway

RUN = Path(__file__).resolve().parent
gateway = create_network_gateway(NetworkPolicy(allowed_domains=("api.github.com",), dns_resolver="cloudflare_doh", allowed_content_types=("application/json",), total_timeout_seconds=12))
report = {"started_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"), "pages": []}
for page in (1, 2):
    url = f"https://api.github.com/repos/vllm-project/vllm/security-advisories?per_page=10&state=published&page={page}"
    response = gateway.fetch(url, max_redirect_hops=0)
    assert response.status_code == 200
    (RUN / f"vendor_pagination_page_{page}.json").write_bytes(response.body)
    report["pages"].append({"requested_page": page, "status": response.status_code, "bytes": len(response.body), "sha256": hashlib.sha256(response.body).hexdigest(),
        "ids": [item["ghsa_id"] for item in json.loads(response.body)],
        "link": next((value for key, value in response.redacted_headers.items() if key.casefold() == "link"), None)})
report["ended_at"] = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
(RUN / "vendor_pagination_probe.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report))
