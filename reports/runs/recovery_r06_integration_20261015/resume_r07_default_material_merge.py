"""Preserve one frozen probe's EOF bytes through an exact evidence-file attribute."""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
RELATIVE = "reports/runs/recovery_r07_idempotency_scope_20261016/probes/conftest.py"


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def now():
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


assert git("rev-parse", "HEAD").decode().strip() == "be398bf0ba39eee2ad8c0db494839b4e6709ca5d"
assert git("rev-parse", "MERGE_HEAD").decode().strip() == "9982c5ec444cef429cef554bdd2e85253c1afe82"
assert not git("diff", "--name-only", "--diff-filter=U").strip()
original_blob = git("show", "9982c5ec444cef429cef554bdd2e85253c1afe82:" + RELATIVE)
assert git("show", ":" + RELATIVE) == original_blob
assert (ROOT / RELATIVE).read_bytes() == original_blob
assert (RUN / "r07_default_fixed_staged_check.log").read_text().splitlines() == [RELATIVE + ":12: new blank line at EOF."]
attributes_path = ROOT / ".gitattributes"
before = attributes_path.read_bytes()
rule = RELATIVE.encode() + b" -text whitespace=-blank-at-eof\n"
assert rule.rstrip(b"\n") not in before.splitlines()
attributes_path.write_bytes(before.rstrip(b"\r\n") + b"\n" + rule)
subprocess.run(["git", "add", "--", ".gitattributes"], cwd=ROOT, check=True, capture_output=True)
with (RUN / "r07_default_fixed_material_check.log").open("xb") as output:
    checked = subprocess.run(["git", "diff", "--cached", "--check"], cwd=ROOT, stdout=output, stderr=subprocess.STDOUT)
assert checked.returncode == 0
assert not any(path.endswith(".pyc") for path in git("diff", "--cached", "--name-only").decode().splitlines())
assert git("show", ":" + RELATIVE) == original_blob
with (RUN / "r07_default_fixed_commit.log").open("xb") as output:
    committed = subprocess.run(["git", "commit", "-m", "G-C integrate reviewed durable enrichment API worker with scoped idempotency"], cwd=ROOT, stdout=output, stderr=subprocess.STDOUT, timeout=90)
assert committed.returncode == 0
receipt_path = RUN / "r07_default_fixed_integration_receipt.json"
receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
receipt.update({"ended_at": now(), "integrated_sha": git("rev-parse", "HEAD").decode().strip(), "commit_exit_code": committed.returncode, "source_conflicts": 0, "user_buildinfo_unchanged": hashlib.sha256((ROOT / "frontend/tsconfig.tsbuildinfo").read_bytes()).hexdigest() == "3c587edfd308fb5cf04efa6e2d87b7005ef28c8c656842059b2eca405738e43d", "exact_raw_eof_rule": {"path": RELATIVE, "sha256": hashlib.sha256(original_blob).hexdigest(), "reason": "preserve frozen raw probe extra EOF; no code/test bytes changed", "global_whitespace_disabled": False}, "root_attribute_union": "exact baseline rules plus candidate evidence rules; source conflict absent", "initial_material_check_exit_code": 2, "fixed_material_check_exit_code": checked.returncode})
assert receipt["user_buildinfo_unchanged"]
receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps(receipt))
