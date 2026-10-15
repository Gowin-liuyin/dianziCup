"""Copy one recorded public response without changing its bytes."""

import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

root = Path(__file__).resolve().parents[3]
original = Path("D:/dianzi/reports/runs/recovery_r04_sources_20261015")
body = (original / "vllm_vendor_first.body.json").read_bytes()
receipt = json.loads((original / "vllm_vendor_first.receipt.json").read_bytes())
digest = hashlib.sha256(body).hexdigest()
assert digest == receipt["body_sha256"]
fixture = root / "fixtures/recorded/vllm_vendor_20261015_public.json"
fixture.write_bytes(body)
provenance = {
    "source": receipt["url"],
    "observed_started_at": receipt["started_at"],
    "observed_ended_at": receipt["ended_at"],
    "http_status": receipt["status"],
    "body_bytes": len(body),
    "body_sha256": digest,
    "recorded_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
    "original_receipt": "reports/runs/recovery_r04_sources_20261015/vllm_vendor_first.receipt.json",
    "is_synthetic": False,
    "usage": "recorded isolated unit/contract sample; not live pipeline acceptance or gold",
    "request_mode": "anonymous public GitHub repository advisory diagnostic",
}
fixture.with_suffix(".provenance.json").write_text(
    json.dumps(provenance, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
)
print(json.dumps({"sha256": digest, "bytes": len(body)}))
