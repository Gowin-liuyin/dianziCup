"""通过专用适配器执行一次已确认的账户只读验证；仅保存脱敏元数据。"""

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from ai_intel.assets.fofa_relay import FofaRelayClient, FofaRelayConfig, FofaRelayError

started_at = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
receipt: dict[str, object] = {
    "started_at": started_at,
    "provider_id": "fofa_relay",
    "provider_kind": "third_party_relay",
    "operation": "read_only_account_validation",
    "authenticated_request_limit": 1,
    "asset_searches": 0,
    "scans": 0,
    "model_calls": 0,
    "fee": "unknown",
    "is_synthetic": False,
}
try:
    account = FofaRelayClient(FofaRelayConfig.from_environment()).probe_account()
    receipt.update(
        account_validated=True,
        status=account.status,
        today_counter_present=account.today_remaining is not None,
        total_counter_present=account.total_remaining is not None,
    )
except FofaRelayError as error:
    receipt.update(account_validated=False, error_code=error.code, retryable=error.retryable)
receipt["finished_at"] = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
Path(__file__).with_name("account_probe_receipt.json").write_text(
    json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(json.dumps(receipt, ensure_ascii=True))
