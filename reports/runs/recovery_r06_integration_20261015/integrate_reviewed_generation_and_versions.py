"""Merge frozen reviewed components while retaining narrow raw-evidence attributes."""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent


def git(*arguments):
    return subprocess.check_output(["git", *arguments], cwd=ROOT, text=True, encoding="utf-8").strip()


def now():
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


assert git("branch", "--show-current") == "codex/full-delivery-recovery"
assert git("remote", "get-url", "origin") == "https://github.com/Gowin-liuyin/dianziCup.git"
assert git("rev-parse", "HEAD") == "cc1b1d302e22048f567475b7084bcd5490761ed2"
assert not git("diff", "--cached", "--name-only")
assert not git("status", "--porcelain", "--", "backend/src", "backend/tests", "backend/pyproject.toml", "backend/uv.lock", ".gitattributes")
packages = [
    ("generation-predispatch-timeout", "df0faafb64327be190803089f0058f9b5dc2427b", "reports/reviews/recovery/G-B-R05-generation-predispatch-timeout-review-1.md", "reports/runs/recovery_r05_generation_predispatch_timeout_review_1_20261016/artifact_manifest.json", "6b4a9062c1aeb9fb042b58e8ead1b30c4c63798a2b5dbb79361cdd3b33b260f0", "G-C integrate reviewed shared predispatch timeout classification"),
    ("ecosystem-version-ranges", "8f5fe818774349b41b0b5aceb45d69ba81410678", "reports/reviews/recovery/G-D-R11-version-ranges-review-1-recheck.md", "reports/runs/recovery_r11_version_ranges_review1_fix1_20261016/artifact_manifest.json", "4d0344b9474b6017bb06a3f1d11edc90f19c78a67de180b1c083c86b06aa0f1d", "G-D prepare reviewed ecosystem version ranges with strict unknown branch handling"),
]
receipt = {"started_at": now(), "before_sha": git("rev-parse", "HEAD"), "scope": "component integration; G-C/G-D and whole R cards not accepted", "push_attempts": 0, "packages": []}
for name, target, report, manifest, expected, message in packages:
    assert hashlib.sha256((ROOT / manifest).read_bytes()).hexdigest() == expected
    report_bytes = (ROOT / report).read_bytes()
    argv = ["git", "merge", "--no-ff", target, "-m", message]
    started = now()
    with (RUN / (name + "_reviewed_merge.log")).open("xb") as output:
        result = subprocess.run(argv, cwd=ROOT, stdout=output, stderr=subprocess.STDOUT, timeout=120)
    item = {"package": name, "target_material_sha": target, "review_report": report, "review_report_sha256": hashlib.sha256(report_bytes).hexdigest(), "review_manifest_sha256": expected, "argv": argv, "started_at": started, "ended_at": now(), "merge_exit_code": result.returncode, "head_after": git("rev-parse", "HEAD")}
    receipt["packages"].append(item)
    (RUN / "generation_and_versions_integration_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    if result.returncode:
        unresolved = git("diff", "--name-only", "--diff-filter=U").splitlines()
        assert unresolved == [".gitattributes"], "unexpected semantic conflict requires root investigation"
        base = git("show", ":1:.gitattributes").splitlines()
        ours = git("show", ":2:.gitattributes").splitlines()
        theirs = git("show", ":3:.gitattributes").splitlines()
        assert set(base) <= set(ours) and set(base) <= set(theirs)
        additions = [line for line in theirs if line not in ours]
        assert all(not line or line.startswith("reports/runs/recovery_r11_version_ranges") or line.startswith("reports/tasks/R11-version-ranges") or line.startswith("reports/runs/recovery_r05_generation_predispatch_timeout_fix_20261016/") for line in additions)
        (ROOT / ".gitattributes").write_text("\n".join(ours + additions) + "\n", encoding="utf-8")
        subprocess.run(["git", "add", "--", ".gitattributes"], cwd=ROOT, check=True)
        assert not git("diff", "--name-only", "--diff-filter=U")
        with (RUN / (name + "_attributes_commit.log")).open("xb") as output:
            subprocess.run(["git", "commit", "-m", message], cwd=ROOT, stdout=output, stderr=subprocess.STDOUT, check=True)
        item["attribute_union"] = {"added_exact_lines": additions, "resolved_at": now(), "head_after": git("rev-parse", "HEAD")}
    item["final_head"] = git("rev-parse", "HEAD")
    (RUN / "generation_and_versions_integration_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
receipt["ended_at"] = now()
(RUN / "generation_and_versions_integration_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"head": git("rev-parse", "HEAD"), "merged_components": len(packages), "push_attempts": 0}))
