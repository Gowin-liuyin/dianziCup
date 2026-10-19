"""Four fixed official-source probes; no retry, redirect, credential or product success claim."""

import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root / "backend/src"))

from ai_intel.infrastructure.network import NetworkPolicy, create_network_gateway

run = Path(__file__).resolve().parent
outside = Path("D:/dianzi-runtime-cache/01a13a70-858c-7d92-8070-0b2693ad7fc4/r06-auxiliary-source-probes")
outside.mkdir(parents=True, exist_ok=True)
clock = ZoneInfo("Asia/Shanghai")
targets = (
    ("cnnvd_official_entry", "https://www.cnnvd.org.cn/web/index.html"),
    ("cnvd_official_entry", "https://www.cnvd.org.cn/"),
    ("epss_single_cve", "https://api.first.org/data/v1/epss?cve=CVE-2024-37032"),
    ("cisa_kev_json", "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"),
)
gateway = create_network_gateway(NetworkPolicy(
    allowed_domains=("www.cnnvd.org.cn", "www.cnvd.org.cn", "api.first.org", "www.cisa.gov"),
    max_response_bytes=4 * 1024**2,
    allowed_content_types=("text/html", "application/json", "text/plain"),
    total_timeout_seconds=12,
    dns_resolver="cloudflare_doh",
), max_concurrent_requests=1)
receipts = []
for name, uri in targets:
    receipt = {"name": name, "request_url": uri, "started_at": datetime.now(clock).isoformat(timespec="seconds"), "maximum_attempts": 1, "redirects_permitted": 0, "product_ingestion": False, "model_calls": 0}
    try:
        result = gateway.fetch(uri, max_redirect_hops=0)
        destination = outside / (name + ".body")
        assert not destination.exists(), "do not overwrite a previous original response"
        destination.write_bytes(result.body)
        receipt.update({"http_status": result.status_code, "content_type": result.content_type, "bytes": len(result.body), "sha256": hashlib.sha256(result.body).hexdigest(), "original_body_outside_git": str(destination), "headers": result.redacted_headers})
        if result.status_code == 200 and result.content_type == "application/json":
            parsed = json.loads(result.body)
            receipt["root_keys"] = sorted(parsed) if isinstance(parsed, dict) else []
            if name == "epss_single_cve" and isinstance(parsed, dict):
                receipt["record_count"] = len(parsed.get("data", []))
            if name == "cisa_kev_json" and isinstance(parsed, dict):
                receipt["record_count"] = len(parsed.get("vulnerabilities", []))
                receipt["catalog_version"] = parsed.get("catalogVersion")
    except Exception as error:
        receipt.update({"error_type": type(error).__name__, "error_code": getattr(error, "code", "probe_failed"), "details": "withheld"})
    receipt["ended_at"] = datetime.now(clock).isoformat(timespec="seconds")
    receipts.append(receipt)
    (run / "probe_receipt.json").write_text(json.dumps({"code_sha": "0a45185ae3ffb73a6d186b98421e26a52f78bfc6", "maximum_total_requests": 4, "paid_requests": 0, "probes": receipts}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: receipt.get(key) for key in ("name", "http_status", "error_type", "bytes", "record_count")}), flush=True)
