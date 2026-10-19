"""Integrate fixed reviewed slices without treating them as whole-stage acceptance."""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
PACKAGES = (
    ("R07-public-signals", "facf6cce653de318ac966e71ac62b479e562aa61",
     "reports/reviews/recovery/G-C-R07-public-signals-review-1-recheck.md",
     "G-C R07: integrate independently rechecked score and taxonomy candidates"),
    ("R20-startup-boundary", "535c0a537bc24cb52c64511c72eeb4ea3ae5bc34",
     "reports/reviews/recovery/G-F-R20-startup-fix-review-1.md",
     "R20: integrate reviewed fail-closed readiness and bounded PDF imports"),
    ("R17-event-detail", "6472d816471a8c8ff176745d199ae4a3ef73270f",
     "reports/reviews/recovery/G-E-R17-event-detail-ui-review-1-recheck.md",
     "R17: integrate independently rechecked evidence detail and touch targets"),
)


def git(*arguments):
    return subprocess.check_output(["git", *arguments], cwd=ROOT, text=True, encoding="utf-8").strip()


def now():
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


assert git("branch", "--show-current") == "codex/full-delivery-recovery"
assert git("remote", "get-url", "origin") == "https://github.com/Gowin-liuyin/dianziCup.git"
assert git("rev-parse", "HEAD") == "349c5e3ec27196257b98cdfcb63c75fb50157978"
assert not git("status", "--porcelain", "--", "backend/src", "backend/tests", "frontend/src", "frontend/e2e", ".gitattributes")
receipt = {"started_at": now(), "before_sha": git("rev-parse", "HEAD"),
           "push_attempts": 0, "stage_gate": "G-C not accepted; per-slice reviewed integration only", "packages": []}
for package, sha, report, message in PACKAGES:
    report_path = ROOT / report
    assert report_path.is_file(), report
    start = now()
    argv = ["git", "merge", "--no-ff", sha, "-m", message]
    with (RUN / (package + "_reviewed_merge.log")).open("xb") as output:
        result = subprocess.run(argv, cwd=ROOT, stdout=output, stderr=subprocess.STDOUT, timeout=120)
    item = {"package": package, "target_material_sha": sha,
            "review_report": report,
            "review_report_sha256": hashlib.sha256(report_path.read_bytes()).hexdigest(),
            "started_at": start, "ended_at": now(), "argv": argv,
            "exit_code": result.returncode, "head_after": git("rev-parse", "HEAD")}
    receipt["packages"].append(item)
    (RUN / "public_ui_startup_integration_receipt.json").write_text(
        json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    if result.returncode:
        raise SystemExit(result.returncode)
receipt["ended_at"] = now()
(RUN / "public_ui_startup_integration_receipt.json").write_text(
    json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"head": git("rev-parse", "HEAD"), "merged_slices": len(PACKAGES), "push_attempts": 0}))
