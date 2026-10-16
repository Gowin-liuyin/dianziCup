"""Preserve the initial seal and narrowly allow two raw CRLF evidence files."""

import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
initial = RUN / "artifact_manifest_initial.json"
assert not initial.exists()
initial.write_bytes((RUN / "artifact_manifest.json").read_bytes())
old_members = json.loads(initial.read_text(encoding="utf-8"))["members"]
for member in old_members:
    assert hashlib.sha256((ROOT / member["path"]).read_bytes()).hexdigest() == member["sha256"]
attributes = RUN / ".gitattributes"
attributes.write_text(attributes.read_text(encoding="utf-8") + "owned_database.json whitespace=cr-at-eol\nsynthetic_source_blobs/raw_manifest.jsonl whitespace=cr-at-eol\n", encoding="utf-8", newline="\n")
report = ROOT / "reports/tasks/R12-production-hybrid-migration.md"
now = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
report.write_text(report.read_text(encoding="utf-8") + f"\n{now} 修订：第一次材料check因两条原raw CRLF回执失败并阻断commit，原material_check.log保留；仅该run owned_database.json及synthetic_source_blobs/raw_manifest.jsonl加cr-at-eol归档规则，不裁字节/不改全局检查。initial manifest保留68项历史原hash；最终manifest追加这一修订与归档工具/失败log。\n", encoding="utf-8", newline="\n")
files = [report] + [path for path in RUN.rglob("*") if path.is_file() and "__pycache__" not in path.parts and path.name != "artifact_manifest.json"]
members = [{"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for path in sorted(files)]
(RUN / "artifact_manifest.json").write_text(json.dumps({"code_sha": "ed0e14a03a06ed104f23afd0be5407d873ed8edf", "created_at": now, "initial_manifest_sha256": hashlib.sha256(initial.read_bytes()).hexdigest(), "members": members, "excluded": ["__pycache__", "private credential reference", "model/tool caches", "holdout"]}, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps({"final_members": len(members), "created_at": now}))
