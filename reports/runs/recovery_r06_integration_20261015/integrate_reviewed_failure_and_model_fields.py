"""Integrate independently rechecked source receipts and unverified model candidates."""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent


def git(*arguments):
    return subprocess.check_output(["git", *arguments], cwd=ROOT, text=True, encoding="utf-8").strip()


def now():
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


assert git("branch", "--show-current") == "codex/full-delivery-recovery"
assert git("remote", "get-url", "origin") == "https://github.com/Gowin-liuyin/dianziCup.git"
assert git("rev-parse", "HEAD") == "595a13197a2c1bba6ad79957f8fde3750ba2a6c6"
assert not git("status", "--porcelain", "--", "backend/src", "backend/tests", "frontend/src", "frontend/e2e", ".gitattributes")
packages = (
    ("source-failure-receipts", "b7817239022caed52ba6b8912b2d827c58a60181",
     "reports/reviews/recovery/G-C-R06-failed-response-review-1-recheck.md",
     "G-C R06: retain failed upstream bytes before parsing without advancing cursors"),
    ("model-field-candidates", "ef24758bd8e9e3e1e8e24760d330a9ffe62af341",
     "reports/reviews/recovery/G-C-R07-model-fields-review-1-recheck.md",
     "G-C R07: integrate reviewed pinned taxonomy and condition-preserving candidates"),
)
receipt = {"started_at": now(), "before_sha": git("rev-parse", "HEAD"), "push_attempts": 0,
           "stage_gate": "G-C not accepted; model candidate preparation is not live fact support", "packages": []}
for name, sha, report, message in packages:
    report_bytes = (ROOT / report).read_bytes()
    argv = ["git", "merge", "--no-ff", sha, "-m", message]
    started = now()
    with (RUN / (name + "_reviewed_merge.log")).open("xb") as output:
        result = subprocess.run(argv, cwd=ROOT, stdout=output, stderr=subprocess.STDOUT, timeout=120)
    receipt["packages"].append({"package": name, "target_material_sha": sha, "review_report": report,
        "review_report_sha256": hashlib.sha256(report_bytes).hexdigest(), "argv": argv,
        "started_at": started, "ended_at": now(), "exit_code": result.returncode,
        "head_after": git("rev-parse", "HEAD")})
    (RUN / "failure_and_model_fields_integration_receipt.json").write_text(
        json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    if result.returncode:
        raise SystemExit(result.returncode)
receipt["ended_at"] = now()
(RUN / "failure_and_model_fields_integration_receipt.json").write_text(
    json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"head": git("rev-parse", "HEAD"), "merged_slices": len(packages), "push_attempts": 0}))
