"""比较同一固定网关在两个宿主的匿名公源访问；不放宽 TLS/DNS 边界。"""

import json
import platform
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from ai_intel.infrastructure.dns_resolver import CloudflareDohResolver
from ai_intel.infrastructure.network import NetworkPolicy, RequestDeadline, create_network_gateway

ROOT = Path(__file__).resolve().parents[3]
RUN = ROOT / "reports/runs/recovery_r04_source_jobs_20261015"
LABEL = platform.system().lower()
receipt = {"os": LABEL, "started_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"), "probes": []}
for kind in ("dns", "get"):
    started = time.monotonic()
    try:
        if kind == "dns":
            result = {"addresses": CloudflareDohResolver()("services.nvd.nist.gov", RequestDeadline(time.monotonic() + 12))}
        else:
            gateway = create_network_gateway(NetworkPolicy(allowed_domains=("services.nvd.nist.gov",), dns_resolver="cloudflare_doh", total_timeout_seconds=12))
            response = gateway.fetch("https://services.nvd.nist.gov/rest/json/cves/2.0?keywordSearch=ollama&resultsPerPage=1&startIndex=0", max_redirect_hops=0)
            result = {"status": response.status_code, "bytes": len(response.body)}
    except Exception as error:
        result = {"error_type": type(error).__name__, "error_code": getattr(error, "code", "diagnostic_failed")}
    receipt["probes"].append({"kind": kind, "elapsed_seconds": time.monotonic() - started, **result})
receipt["ended_at"] = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
path = RUN / ("gateway_probe_" + LABEL + ".json")
assert not path.exists()
path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
print(json.dumps(receipt))
