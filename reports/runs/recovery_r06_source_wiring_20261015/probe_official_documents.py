"""Two fixed public document GETs, bounded bytes/time and no retry or model use."""

import hashlib
import json
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from ai_intel.infrastructure.network import NetworkPolicy, create_network_gateway

run = Path(__file__).resolve().parent
gateway = create_network_gateway(NetworkPolicy(
    allowed_domains=("nvlpubs.nist.gov", "www.cac.gov.cn"),
    allowed_content_types=("application/pdf", "text/html"),
    max_response_bytes=5 * 1024 * 1024, total_timeout_seconds=12,
    dns_resolver="cloudflare_doh",
), max_concurrent_requests=1)
sources = (
    ("nist_ai_rmf", "https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.100-1.pdf"),
    ("cac_generative_ai", "https://www.cac.gov.cn/2023-07/13/c_1690898327029107.htm"),
)
for index, (name, url) in enumerate(sources):
    if index:
        time.sleep(7)
    started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
    result = gateway.fetch(url, max_redirect_hops=0)
    (run / (name + ".body")).write_bytes(result.body)
    receipt = {"name": name, "url": url, "started_at": started,
               "ended_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
               "status": result.status_code, "bytes": len(result.body),
               "sha256": hashlib.sha256(result.body).hexdigest(),
               "content_type": result.content_type,
               "scope": "official source shape probe only; not worker/PG/UI live"}
    (run / (name + ".json")).write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt), flush=True)
