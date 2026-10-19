"""Two bounded account-only requests retain quota fields and no identity or credential data."""

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


def now():
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def scalar_fields(mapping, names):
    if not isinstance(mapping, dict):
        return {}
    return {
        name: mapping[name]
        for name in names
        if name in mapping and type(mapping[name]) in {int, float, bool, str, type(None)}
    }


def main():
    observations = []
    providers = (
        ("quake", "https://quake.360.net", "/api/v3/user/info", "X-QuakeToken", "GET"),
        ("zoomeye", "https://api.zoomeye.ai", "/v2/userinfo", "API-KEY", "POST"),
    )
    for provider, origin, path, header, method in providers:
        started = now()
        entry = {"provider": provider, "endpoint": origin + path, "method": method,
                 "started_at": started, "asset_queries": 0}
        try:
            key = os.environ["DIANZI_ACCOUNT_" + provider.upper() + "_KEY"]
            gateway = create_network_gateway(
                NetworkPolicy(
                    (origin.removeprefix("https://"),), max_response_bytes=65536,
                    allowed_content_types=("application/json",), total_timeout_seconds=15,
                    dns_resolver="cloudflare_doh",
                ),
                OriginCredentials(origin, headers={header: SecretStr(key)}),
                max_concurrent_requests=1,
            )
            response = (gateway.fetch(origin + path, max_redirect_hops=0) if method == "GET"
                        else gateway.post_json(origin + path, b"{}"))
            entry.update(http_status=response.status_code, response_bytes=len(response.body),
                         response_sha256=hashlib.sha256(response.body).hexdigest())
            payload = strict_json_object(response.body, 65536)
            code = payload.get("code")
            entry["business_code"] = code if type(code) in {int, str} else None
            if response.status_code == 200 and code == (0 if provider == "quake" else 60000):
                content = payload.get("data")
                if provider == "quake":
                    entry["quota"] = scalar_fields(content, ("credit", "persistent_credit"))
                elif isinstance(content, dict):
                    entry["quota"] = scalar_fields(
                        content.get("subscription"), ("plan", "points", "zoomeye_points", "end_date")
                    )
                entry["state"] = "account_verified" if entry.get("quota") else "quota_fields_missing"
            else:
                entry["state"] = "account_rejected"
        except Exception as error:
            entry.update(state="request_failed", error_type=type(error).__name__)
        entry["ended_at"] = now()
        observations.append(entry)
    result = {"recorded_at": now(), "maximum_requests": 2, "attempted_requests": 2,
              "asset_searches": 0, "scans": 0, "model_calls": 0, "fee": "unknown",
              "raw_responses_saved": False, "identity_fields_saved": False,
              "observations": observations}
    (RUN / "account_receipt.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
