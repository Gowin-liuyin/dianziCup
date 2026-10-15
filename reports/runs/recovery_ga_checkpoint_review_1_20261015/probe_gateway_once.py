"""One bounded, public NVD GET through the frozen production gateway."""
import hashlib
import json
from pathlib import Path
from ai_intel.infrastructure.network import NetworkPolicy, NetworkRequestError, NetworkPolicyViolation, create_network_gateway

gateway=create_network_gateway(NetworkPolicy(allowed_domains=('services.nvd.nist.gov',),allowed_content_types=('application/json',),total_timeout_seconds=12,dns_resolver='cloudflare_doh'),max_concurrent_requests=1)
try:
    result=gateway.fetch('https://services.nvd.nist.gov/rest/json/cves/2.0?cveId=CVE-2024-28224',max_redirect_hops=0)
    metadata=dict(status=result.status_code,bytes=len(result.body),sha256=hashlib.sha256(result.body).hexdigest(),request_fingerprint_sha256=result.request_fingerprint_sha256,dns_resolver='explicit cloudflare_doh',paid_calls=0)
    Path('D:/dianzi/reports/runs/recovery_ga_checkpoint_review_1_20261015/gateway_one_get.json').write_text(json.dumps(metadata,indent=2))
    print(json.dumps(metadata))
except (NetworkRequestError,NetworkPolicyViolation) as error:
    print(json.dumps(dict(error_code=error.code,paid_calls=0)))
    raise SystemExit(4)
