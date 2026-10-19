"""Preserve Playwright raw failure bytes with one run-scoped whitespace exemption."""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
receipt_path = RUN / "graph_app_migrations_integration_receipt.json"
receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
assert receipt["packages"][-1]["package"] == "r17_default_graph_app"
assert subprocess.check_output(["git", "diff", "--name-only", "--diff-filter=U"], cwd=ROOT).strip() == b""
attrs = ROOT / ".gitattributes"
rule = "reports/runs/recovery_r17_graph_app_20261016/** whitespace=-blank-at-eol"
current = attrs.read_text(encoding="utf-8")
assert rule not in current.splitlines()
attrs.write_text(current.rstrip() + "\n" + rule + "\n", encoding="utf-8", newline="\n")
subprocess.run(["git", "add", "--", ".gitattributes"], cwd=ROOT, check=True)
with (RUN / "r17_default_graph_app_raw_whitespace_commit.log").open("xb") as output:
    subprocess.run(["git", "diff", "--cached", "--check"], cwd=ROOT, stdout=output, stderr=subprocess.STDOUT, check=True)
    subprocess.run(["git", "commit", "-m", "G-E integrate reviewed graph navigation into default App"], cwd=ROOT, stdout=output, stderr=subprocess.STDOUT, check=True)
item = receipt["packages"][-1]
item["integration_note"] = {"recorded_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"), "original_raw_diff_check_exit_code": 2, "reason": "Playwright original failed snapshots have trailing spaces in captured source excerpts; preserve raw bytes", "only_added_whitespace_attribute": rule, "source_diff_check_exit_code": 0}
item["integrated_sha"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
original_script = (RUN / "integrate_reviewed_graph_app_migrations.py").read_text(encoding="utf-8")
head = item["integrated_sha"]
continuation = original_script.replace('assert git("rev-parse", "HEAD") == "48b56033cf5daf3ce8cfaa710c0acbda7cc2356e"', 'assert git("rev-parse", "HEAD") == "' + head + '"').replace('for name, target, report, report_hash, manifest, manifest_hash, message in packages:', 'for name, target, report, report_hash, manifest, manifest_hash, message in packages[2:]:')
continuation = continuation.replace('receipt = {"started_at": now(), "before_sha": git("rev-parse", "HEAD"), "scope": "reviewed slices only; no stage/whole-task acceptance", "push": "not_run", "packages": []}', 'receipt = json.loads((RUN / "graph_app_migrations_integration_receipt.json").read_text(encoding="utf-8"))')
path = RUN / "continue_forward_migration_merge.py"
path.write_text(continuation, encoding="utf-8", newline="\n")
print(json.dumps({"graph_app_integrated_sha": head, "continuation_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}))
subprocess.run([str(ROOT / "backend/.venv/Scripts/python.exe"), str(path)], cwd=ROOT, check=True)
