"""Preserve the new independent timestamp red with exact input and original timestamps."""

import hashlib
import json
from pathlib import Path

RUN = Path(__file__).resolve().parent
ORIGIN = Path("D:/wt/r07-input-review1/reports/runs/recovery_r07_input_review1_20261016")
files = []
for name in ("explicit_timestamp_7aeb85_probe.xml", "explicit_timestamp_7aeb85_probe.log",
             "explicit_timestamp_7aeb85_probe.command.json", "test_review_probe.py"):
    raw = (ORIGIN / name).read_bytes()
    target = RUN / ("original_" + name)
    target.write_bytes(raw)
    files.append({"origin": str(ORIGIN / name), "snapshot": target.name,
                  "raw_sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)})
(RUN / "original_timestamp_must_manifest.json").write_text(json.dumps({
    "source_sha": "7aeb85ae8277c048fb762dbc705436602cb18f9d", "files": files,
    "reviewer_original_inputs_edited": False,
}, indent=2), encoding="utf-8")
print(json.dumps(files))
