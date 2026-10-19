"""Merge the fixed durable entry snapshot under its independently sealed review."""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
BASELINE = "be398bf0ba39eee2ad8c0db494839b4e6709ca5d"
MATERIAL = "9982c5ec444cef429cef554bdd2e85253c1afe82"
SOURCE = "ba69d6cbc2bc4828a56bdc8c7d2f2c95c4dda5ce"
RECEIPT = RUN / "r07_default_fixed_integration_receipt.json"


def now():
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


assert git("rev-parse", "HEAD").decode().strip() == BASELINE
assert git("branch", "--show-current").decode().strip() == "codex/full-delivery-recovery"
assert git("remote", "get-url", "origin").decode().strip() == "https://github.com/Gowin-liuyin/dianziCup.git"
assert not git("diff", "--cached", "--name-only").strip()
assert not git("status", "--porcelain", "--", "backend", "frontend/src", ".gitattributes").strip()
subprocess.run(["git", "merge-base", "--is-ancestor", SOURCE, MATERIAL], cwd=ROOT, check=True, capture_output=True)
report = ROOT / "reports/reviews/recovery/G-C-R07-default-durable-entry-review-1-recheck.md"
manifest = ROOT / "reports/runs/recovery_r07_default_entry_review1_fix1_20261016/review_artifact_manifest.json"
assert digest(report) == "baa2809ffa77a84efba07eb1dda7a3db2aab062812267d38adee253ed0c29d23"
assert digest(manifest) == "90b0af548b77e07260a0507fc0662ef99c36d6f62e801ab1a82b5f4e2facf3ca"
assert digest(ROOT / "reports/runs/recovery_evidence_archive_20261016/archive_followup_12_receipt.json") == "35d9a00a32ae7f945426864377abc8d6d8c5a5ba9295d9e4866d048841ded195"
user_hash = digest(ROOT / "frontend/tsconfig.tsbuildinfo")
assert user_hash == "3c587edfd308fb5cf04efa6e2d87b7005ef28c8c656842059b2eca405738e43d"
receipt = {"started_at": now(), "baseline": BASELINE, "source": SOURCE, "material": MATERIAL, "review_commit": None, "review_report_sha256": digest(report), "review_manifest_sha256": digest(manifest), "stage_accepted": False, "whole_R07_accepted": False, "push": "not_run", "conflicts": []}
with (RUN / "r07_default_fixed_merge.log").open("xb") as output:
    result = subprocess.run(["git", "merge", "--no-commit", "--no-ff", MATERIAL], cwd=ROOT, stdout=output, stderr=subprocess.STDOUT, timeout=90)
receipt["merge_exit_code"] = result.returncode
conflicts = git("diff", "--name-only", "--diff-filter=U").decode().splitlines()
receipt["conflicts"] = conflicts
RECEIPT.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
if result.returncode:
    assert conflicts and all(path.endswith(".gitattributes") for path in conflicts), "retain unexpected merge failure for diagnosis"
    for relative in conflicts:
        ours = git("show", ":2:" + relative)
        theirs = git("show", ":3:" + relative)
        assert b"<<<<<<<" not in ours + theirs
        additions = [line for line in theirs.splitlines() if line and line not in ours.splitlines()]
        assert all(line.startswith(b"reports/") or relative != ".gitattributes" for line in additions)
        merged = ours.rstrip(b"\r\n") + b"\n" + b"\n".join(additions) + (b"\n" if additions else b"")
        (ROOT / relative).write_bytes(merged)
        subprocess.run(["git", "add", "--", relative], cwd=ROOT, capture_output=True, check=True)
        receipt.setdefault("attribute_resolutions", []).append({"path": relative, "ours_sha256": hashlib.sha256(ours).hexdigest(), "theirs_sha256": hashlib.sha256(theirs).hexdigest(), "added_exact_rules": len(additions)})
assert not git("diff", "--name-only", "--diff-filter=U").strip()
with (RUN / "r07_default_fixed_staged_check.log").open("xb") as output:
    checked = subprocess.run(["git", "diff", "--cached", "--check"], cwd=ROOT, stdout=output, stderr=subprocess.STDOUT)
assert checked.returncode == 0
with (RUN / "r07_default_fixed_commit.log").open("xb") as output:
    committed = subprocess.run(["git", "commit", "-m", "G-C integrate reviewed durable enrichment API worker with scoped idempotency"], cwd=ROOT, stdout=output, stderr=subprocess.STDOUT, timeout=90)
assert committed.returncode == 0
receipt.update({"ended_at": now(), "integrated_sha": git("rev-parse", "HEAD").decode().strip(), "commit_exit_code": committed.returncode, "user_buildinfo_unchanged": digest(ROOT / "frontend/tsconfig.tsbuildinfo") == user_hash, "source_conflicts": 0})
assert receipt["user_buildinfo_unchanged"]
RECEIPT.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps(receipt))
