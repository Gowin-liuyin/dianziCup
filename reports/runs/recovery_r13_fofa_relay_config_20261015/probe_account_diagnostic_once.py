"""最后一次同路径只读诊断；仅记录安全字段类型和授权额度数。"""

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

from ai_intel.assets.fofa_relay import ACCOUNT_PATH, RELAY_ORIGIN, FofaRelayConfig
from ai_intel.infrastructure.network import (
    NetworkPolicy,
    NetworkPolicyViolation,
    NetworkRequestError,
    OriginCredentials,
    RequestDeadline,
    TransportResponse,
    create_network_gateway,
)

receipt: dict[str, object] = {
    "started_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
    "operation": "last_read_only_account_diagnostic",
    "authenticated_attempt_number": 2,
    "asset_searches": 0,
    "scans": 0,
    "model_calls": 0,
    "fee": "unknown",
    "is_synthetic": False,
}
config = FofaRelayConfig.from_environment()
gateway = create_network_gateway(
    NetworkPolicy(
        allowed_domains=("fafaapi.info",),
        max_response_bytes=65536,
        allowed_content_types=("application/json",),
        total_timeout_seconds=10,
        dns_resolver="cloudflare_doh",
    ),
    OriginCredentials(config.base_url, query_parameters={"key": config.api_key}),
    max_concurrent_requests=1,
)
transport_request = gateway._transport.request


def record_metadata(
    url: str, addresses: tuple[str, ...], deadline: RequestDeadline, headers: dict[str, str]
) -> TransportResponse:
    response = transport_request(url, addresses, deadline, headers)
    receipt["status_code"] = response.status_code
    for name, value in response.headers.items():
        if name.lower() == "content-type":
            media_type = value.split(";", 1)[0].strip().lower()
            receipt["content_type"] = (
                media_type if re.fullmatch(r"[a-z0-9.+-]+/[a-z0-9.+-]+", media_type) else "invalid"
            )
        if name.lower() == "content-length" and value.isascii() and value.isdigit():
            receipt["declared_body_bytes"] = int(value)
    return response


def safe_shape(payload: object, path: str = "", depth: int = 0) -> list[dict[str, object]]:
    if not isinstance(payload, dict) or depth > 2:
        return []
    result: list[dict[str, object]] = []
    for key, value in list(payload.items())[:30]:
        if (
            not isinstance(key, str)
            or not re.fullmatch(r"[a-zA-Z_][a-zA-Z_0-9]{0,39}", key)
            or config.api_key.get_secret_value() in key
        ):
            continue
        field_path = f"{path}.{key}" if path else key
        field: dict[str, object] = {"field": field_path, "type": type(value).__name__}
        if key == "valid" and type(value) is bool:
            field["boolean"] = value
        if key in ("todayRemaining", "totalRemaining") and type(value) is int:
            field["quota"] = value
        result.append(field)
        result.extend(safe_shape(value, field_path, depth + 1))
    return result


try:
    with patch.object(gateway._transport, "request", record_metadata):
        response = gateway.fetch(RELAY_ORIGIN + ACCOUNT_PATH, max_redirect_hops=0)
    if response.body:
        receipt.update(
            body_bytes=len(response.body),
            body_sha256=hashlib.sha256(response.body).hexdigest(),
        )
        try:
            payload: object = json.loads(response.body)
            receipt["json_shape"] = safe_shape(payload)
        except (ValueError, UnicodeDecodeError, RecursionError):
            receipt["json_valid"] = False
    else:
        receipt["body_read"] = False
except (NetworkRequestError, NetworkPolicyViolation) as error:
    receipt["error_code"] = error.code
receipt["finished_at"] = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
Path(__file__).with_name("account_diagnostic_receipt.json").write_text(
    json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(json.dumps(receipt, ensure_ascii=True))
