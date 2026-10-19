"""Resolve only the old evidence directory's attribute conflict using baseline bytes."""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
relative = "reports/runs/recovery_r11_r08_forward_migrations_20261016/.gitattributes"
assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip() == "99c97815fbbfda73921d28abc50c25ac936053c4"
conflicts = subprocess.check_output(["git", "diff", "--name-only", "--diff-filter=U"], cwd=ROOT, text=True).splitlines()
assert conflicts == [relative]
ours = subprocess.check_output(["git", "show", ":2:" + relative], cwd=ROOT)
theirs = subprocess.check_output(["git", "show", ":3:" + relative], cwd=ROOT)
assert ours == subprocess.check_output(["git", "show", "HEAD:" + relative], cwd=ROOT)
assert ours.splitlines() == [
    b"*.log -text -diff",
    b"*.xml -text -diff",
    b"*.json -text whitespace=trailing-space,space-before-tab,cr-at-eol",
    b"*.jsonl -text whitespace=trailing-space,space-before-tab,cr-at-eol",
]
(ROOT / relative).write_bytes(ours)
subprocess.run(["git", "add", "--", relative], cwd=ROOT, check=True, capture_output=True)
assert not subprocess.check_output(["git", "diff", "--name-only", "--diff-filter=U"], cwd=ROOT)
with (RUN / "pg_assessments_nested_attributes_resolution.log").open("xb") as output:
    subprocess.run(["git", "diff", "--cached", "--check"], cwd=ROOT, stdout=output, stderr=subprocess.STDOUT, check=True)
    subprocess.run(["git", "commit", "-m", "G-D integrate reviewed PG rule assessments and mandatory raw validation"], cwd=ROOT, stdout=output, stderr=subprocess.STDOUT, check=True)
receipt_path = RUN / "assets_pg_assessments_integration_receipt.json"
receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
item = receipt["packages"][-1]
item["nested_attribute_resolution"] = {"path": relative, "ours_sha256": hashlib.sha256(ours).hexdigest(), "theirs_sha256": hashlib.sha256(theirs).hexdigest(), "behavior": "preserve baseline evidence attributes byte for byte"}
item["integrated_sha"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
receipt["ended_at"] = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps({"head": item["integrated_sha"], "source_conflicts": 0, "stage_accepted": False, "push": "not_run"}))
