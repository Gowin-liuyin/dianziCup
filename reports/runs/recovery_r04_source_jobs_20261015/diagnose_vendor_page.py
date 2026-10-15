"""再次有界读取公开厂商页定位字段；仅诊断留档，不写产品事实或游标。"""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from ai_intel.infrastructure.network import NetworkPolicy, create_network_gateway
from ai_intel.ingestion.parsing.parsers import parse_json_document
from ai_intel.ingestion.source_documents import SourceResponse, _prepare_documents
from ai_intel.ingestion.sources.vendor_advisories import normalize_vendor_advisory

RUN = Path(__file__).resolve().parent
URL = "https://api.github.com/repos/vllm-project/vllm/security-advisories?per_page=10&state=published&page=1"
report = {"started_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"), "url": URL, "source_code_sha": "95ba6503dcae4b86ea8fdffea150f1b59a941014"}
gateway = create_network_gateway(NetworkPolicy(allowed_domains=("api.github.com",), dns_resolver="cloudflare_doh", allowed_content_types=("application/json",), total_timeout_seconds=12))
response = gateway.fetch(URL, max_redirect_hops=0)
report.update(http_status=response.status_code, bytes=len(response.body), response_sha256=hashlib.sha256(response.body).hexdigest())
assert response.status_code == 200
(RUN / "vllm_actual_page_10.json").write_bytes(response.body)
report["json_parse_status"] = parse_json_document(response.body).status
report["records"] = []
for record in json.loads(response.body):
    summary = {"ghsa_id": record.get("ghsa_id"), "description_characters": len(record.get("description") or "")}
    try:
        normalize_vendor_advisory(record, repository="vllm-project/vllm")
        summary["normalizer"] = "passed"
    except Exception as error:
        summary.update(normalizer="failed", error_type=type(error).__name__, error=str(error))
    report["records"].append(summary)
try:
    _prepare_documents(SourceResponse("vllm_vendor", response.body, URL, datetime.now(UTC)))
    report["writer_prepare"] = "passed"
except Exception as error:
    report.update(writer_prepare="failed", writer_error_type=type(error).__name__, writer_error=str(error))
report["ended_at"] = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
(RUN / "vllm_actual_page_diagnosis.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(report))
