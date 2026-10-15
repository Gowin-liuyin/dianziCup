"""独立公开NVD样本；无API Key，不读.env或ApplicationSettings。"""

import hashlib
import json
import ssl
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from ai_intel.infrastructure import http_transport
from ai_intel.infrastructure.network import NetworkPolicy, create_network_gateway


log_directory = Path("D:/dianzi/reports/runs/recovery_r03_network_review_1_recheck_2_20261015")
source_url = "https://services.nvd.nist.gov/rest/json/cves/2.0?cveId=CVE-2024-28224"
receipts = []
verify_peer = http_transport._PinnedConnection._verify_peer

for resolver_mode in ("cloudflare_doh",):
    peers = []
    started_at = datetime.now().astimezone().isoformat()
    started = time.monotonic()

    def record_verified_peer(connection, connection_socket):
        verify_peer(connection, connection_socket)
        peers.append({
            "hostname": connection.host,
            "checked_address": connection._address,
            "verified_peer": str(connection_socket.getpeername()[0]),
        })

    receipt = {
        "dns_resolver": resolver_mode,
        "started_at": started_at,
        "requested_url": source_url,
        "configured_timeout_seconds": 10,
        "api_key_supplied": False,
        "verified_peers": peers,
        "fixture_used": False,
    }
    try:
        gateway = create_network_gateway(NetworkPolicy(
            ("services.nvd.nist.gov",),
            total_timeout_seconds=10,
            dns_resolver=resolver_mode,
        ))
        receipt["tls_cert_required"] = gateway._transport._tls_context.verify_mode == ssl.CERT_REQUIRED
        receipt["tls_check_hostname"] = gateway._transport._tls_context.check_hostname
        with patch.object(http_transport._PinnedConnection, "_verify_peer", record_verified_peer):
            result = gateway.fetch(source_url)
        receipt["status_code"] = result.status_code
        receipt["final_url"] = result.final_url
        receipt["body_bytes"] = len(result.body)
        receipt["body_sha256"] = hashlib.sha256(result.body).hexdigest()
        receipt["headers"] = result.redacted_headers
        if result.status_code == 200:
            payload = json.loads(result.body)
            receipt["total_results"] = payload.get("totalResults")
            receipt["cve_ids"] = [item["cve"]["id"] for item in payload.get("vulnerabilities", [])]
            body_path = log_directory / f"nvd_{resolver_mode}.body.json"
            body_path.write_bytes(result.body)
            receipt["body_path"] = str(body_path)
    except Exception as error:
        receipt["error_type"] = type(error).__name__
        receipt["error_code"] = getattr(error, "code", None)
        receipt["error_message"] = str(error)
    receipt["elapsed_seconds"] = time.monotonic() - started
    receipt["finished_at"] = datetime.now().astimezone().isoformat()
    receipts.append(receipt)

print(json.dumps(receipts, ensure_ascii=False, indent=2))
