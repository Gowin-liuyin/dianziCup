"""Perform one fixed-origin account request and retain only quota metadata."""

import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from pydantic import SecretStr

from ai_intel.infrastructure.models.json_output import strict_json_object
from ai_intel.infrastructure.network import NetworkPolicy, OriginCredentials, create_network_gateway

RUN = Path(__file__).resolve().parent
ORIGIN = "https://hunter.qianxin.com"
QUOTA_FIELDS = (
    "rest_equity_point", "rest_free_point", "rest_export_quota",
    "day_free_point", "day_export_quota", "once_export_quota",
)


def now():
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def quota_fields(payload):
    """Exclude personal_info and keep only documented integer quota values."""
    if not isinstance(payload, dict):
        return {}
    return {name: payload[name] for name in QUOTA_FIELDS
            if name in payload and type(payload[name]) is int and payload[name] >= -1}


def main():
    assert quota_fields({"rest_free_point": 499, "day_export_quota": -1,
                         "rest_equity_point": True, "personal_info": {"phone": "fixture"}}) == {
                             "rest_free_point": 499, "day_export_quota": -1}
    receipt = {"provider": "hunter", "started_at": now(), "maximum_requests": 1,
               "endpoint": ORIGIN + "/openApi/userInfo", "method": "GET",
               "official_document": ORIGIN + "/home/helpCenter?r=5-1-4",
               "asset_searches": 0, "scans": 0, "model_calls": 0, "fee": "unknown",
               "raw_response_saved": False, "identity_fields_saved": False}
    try:
        gateway = create_network_gateway(
            NetworkPolicy(("hunter.qianxin.com",), max_response_bytes=65536,
                          allowed_content_types=("application/json",),
                          total_timeout_seconds=15, dns_resolver="cloudflare_doh"),
            OriginCredentials(ORIGIN, query_parameters={
                "api-key": SecretStr(os.environ["DIANZI_ACCOUNT_HUNTER_KEY"])}),
            max_concurrent_requests=1,
        )
        receipt["attempted_requests"] = 1
        response = gateway.fetch(ORIGIN + "/openApi/userInfo", max_redirect_hops=0)
        receipt.update(http_status=response.status_code, response_bytes=len(response.body),
                       response_sha256=hashlib.sha256(response.body).hexdigest())
        if response.status_code != 200:
            receipt["state"] = "account_rejected" if response.status_code in (401, 403) else "http_failure"
        else:
            payload = strict_json_object(response.body, 65536)
            code = payload.get("code")
            receipt["business_code"] = code if type(code) in (int, str) else None
            if type(code) is int and code == 200:
                receipt["quota"] = quota_fields(payload.get("data"))
                receipt["state"] = "account_verified"
                receipt["quota_minus_one_means"] = "no_related_limit_per_official_document"
            else:
                receipt["state"] = "account_rejected"
    except Exception as error:
        receipt.update(state="request_failed", error_type=type(error).__name__)
    receipt["ended_at"] = now()
    (RUN / "account_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt))


if __name__ == "__main__":
    main()
