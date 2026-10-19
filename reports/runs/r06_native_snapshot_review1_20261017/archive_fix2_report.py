"""Retain the exact intermediate report version referenced by the fixed-review seal."""

import hashlib
import json
from pathlib import Path

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
report = ROOT / "reports/reviews/recovery/G-C-R06-native-snapshot-review-1.md"
current_header = "**最新定向复核：材料f4036d3a、CORE37ffe6da / OPS81053fd6的批准修复限定LimitedShip；新审计helper 5bfb9077的三个常量更新也已独审限定Ship。初审c8的needs_changes和所有原红作为历史保留。** 当前范围与限制见第7–8节；仍非R06整卡、实际17keys审计、安装、七门或Source启动通过。"
old_header = "**最新定向复核：材料f4036d3a、CORE37ffe6da / OPS81053fd6的批准修复限定LimitedShip；初审c8的needs_changes和所有原红作为历史保留。** 当前范围与限制见第7节；仍非R06整卡、实际审计、安装、七门或Source启动通过。"
raw = report.read_bytes().split(b"\n## 8.", 1)[0]
raw = raw.replace(current_header.encode(), old_header.encode(), 1)
digest = hashlib.sha256(raw).hexdigest()
assert digest == "1d633da2f2b0179296adc5b70f7a74dd4a7ffb03fe285d147ca2c8f5573ebb34"
target = RUN / "G-C-R06-native-snapshot-review-1.before-helper.md"
target.write_bytes(raw)
(RUN / "report_fix2_archive_manifest.json").write_text(json.dumps({"path": str(target.relative_to(ROOT)), "bytes": len(raw), "sha256": digest, "reconstruction_verified_against_original_seal": True}, indent=2) + "\n")
print(json.dumps({"archived_fix2_report_sha256": digest}))
