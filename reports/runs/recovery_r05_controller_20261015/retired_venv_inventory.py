"""对明确拥有的退役审查环境记录文件hash，不提交第三方工具缓存。"""

import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

run = Path(__file__).resolve().parent
label = sys.argv[1]
assert label in {"before", "after"}
receipt = run / ("retired_review_venvs_" + label + ".json")
assert not receipt.exists()
workspace = Path("D:/dianzi").resolve()
cache = Path("D:/dianzi-runtime-cache/01a13a70-858c-7d92-8070-0b2693ad7fc4/retired-review-venvs/20261015").resolve()
entries = []
for name in ("recovery_r02_persistence_review_1_20261015", "recovery_r05_grounded_answer_review_1_20261015"):
    source = workspace / "reports/runs" / name / "venv"
    destination = cache / name
    assert source.resolve().is_relative_to(workspace) and destination.resolve().is_relative_to(cache)
    target = source if label == "before" else destination
    assert target.is_dir()
    records = []
    for path in sorted(target.rglob("*")):
        if path.is_file():
            assert path.resolve().is_relative_to(target.resolve()), "unexpected outside link"
            records.append({"path": path.relative_to(target).as_posix(), "bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    encoded = json.dumps(records, sort_keys=True).encode()
    entries.append({"source": str(source), "destination": str(destination), "file_count": len(records), "bytes": sum(item["bytes"] for item in records), "inventory_sha256": hashlib.sha256(encoded).hexdigest(), "files": records})
if label == "after":
    prior = json.loads((run / "retired_review_venvs_before.json").read_text(encoding="utf-8"))
    for before, after in zip(prior["entries"], entries, strict=True):
        assert before == after, "retired environment bytes changed"
receipt.write_text(json.dumps({"recorded_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"), "phase": label, "entries": entries}, indent=2), encoding="utf-8")
print(json.dumps({"phase": label, "file_counts": [item["file_count"] for item in entries], "hashes": [item["inventory_sha256"] for item in entries]}))
