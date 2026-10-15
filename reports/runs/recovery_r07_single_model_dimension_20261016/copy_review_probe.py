"""Preserve the previous independent review probe byte for byte."""

import hashlib
import json
from pathlib import Path

RUN_ROOT = Path(__file__).resolve().parent
source = Path("D:/wt/r07-model-fields-review-1-recheck/reports/runs/recovery_r07_model_fields_review_1_recheck_20261016/test_gateway_independent.py")
target = RUN_ROOT / source.name
target.write_bytes(source.read_bytes())
result = {
    "source": str(source),
    "target": str(target),
    "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
    "copied_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
    "size_bytes": target.stat().st_size,
}
(RUN_ROOT / "review_probe_copy.json").write_text(
    json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n"
)
assert result["sha256"] == result["copied_sha256"]
print(json.dumps(result))
