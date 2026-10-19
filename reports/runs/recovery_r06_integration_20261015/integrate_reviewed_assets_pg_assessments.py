"""Merge two reviewed slices and record exact code, material, and review identities."""

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


assert git("rev-parse", "HEAD") == "b502b7ea4a2ffdeca24b8edc7fa8a33cc0980457"
assert git("branch", "--show-current") == "codex/full-delivery-recovery"
assert git("remote", "get-url", "origin") == "https://github.com/Gowin-liuyin/dianziCup.git"
assert not git("diff", "--cached", "--name-only")
assert not git("status", "--porcelain", "--", "backend", "frontend/src", ".gitattributes")
user_hash = hashlib.sha256((ROOT / "frontend/tsconfig.tsbuildinfo").read_bytes()).hexdigest()
packages = [
    ("asset_ui", "f9f041056ac717c6be2287a4ad97058538adce66", "a25fd81c50f0ea14f44e7fda2c3edac5cab74d48", "reports/reviews/recovery/G-E-R17-assets-workbench-review-1-recheck.md", "b82c7f2fec2c5599bcfb8978677bb65d3704eac4ce80b204652171e76fbd0570", "reports/runs/recovery_r17_assets_review1_fix1_20261016/raw_manifest.json", "85be63ac7f2f120a1f155c28b165cfd395e04e21614f794d73215832f8055873", "G-E integrate reviewed asset inventory workbench scope clearing"),
    ("pg_rules_assessments", "6b10f2c4ed013f4375d51fc31e1cb317409730ac", "2ddc8fe2ff3e7becfad3b1774a10407911eacbe6", "reports/reviews/recovery/G-D-R11-pg-assessments-review-1-recheck.md", "a7143362b1e655e613409e9fd9fdf7cf2e701d72e7862e4e60e1f9a96e0a70c0", "reports/runs/recovery_r11_pg_assessments_review1_fix1_20261016/artifact_manifest.json", "eeb9d5e428543770065b7a8213a831f3809638f67ec845b03c1bbbe090bb2b20", "G-D integrate reviewed PG rule assessments and mandatory raw validation"),
]
receipt = {"started_at": now(), "before_sha": git("rev-parse", "HEAD"), "scope": "reviewed slices only; no full task/stage gate", "push": "not_run", "packages": []}
destination = RUN / "assets_pg_assessments_integration_receipt.json"
for name, target, code, report, report_hash, manifest, manifest_hash, message in packages:
    assert hashlib.sha256((ROOT / report).read_bytes()).hexdigest() == report_hash
    assert hashlib.sha256((ROOT / manifest).read_bytes()).hexdigest() == manifest_hash
    argv = ["git", "merge", "--quiet", "--no-ff", target, "-m", message]
    with (RUN / (name + "_reviewed_merge.log")).open("xb") as output:
        started = now()
        result = subprocess.run(argv, cwd=ROOT, stdout=output, stderr=subprocess.STDOUT, timeout=90)
    item = {"package": name, "code_sha": code, "material_sha": target, "review_commit_sha": None, "report": report, "report_sha256": report_hash, "manifest_sha256": manifest_hash, "started_at": started, "ended_at": now(), "exit_code": result.returncode}
    receipt["packages"].append(item)
    destination.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
    if result.returncode:
        unresolved = git("diff", "--name-only", "--diff-filter=U").splitlines()
        assert unresolved == [".gitattributes"], "unexpected conflict; leave unchanged for root review"
        ours = git("show", ":2:.gitattributes").splitlines()
        theirs = git("show", ":3:.gitattributes").splitlines()
        additions = [line for line in theirs if line not in ours]
        assert all(not line or line.startswith("reports/") for line in additions)
        (ROOT / ".gitattributes").write_text("\n".join(ours + additions) + "\n", encoding="utf-8", newline="\n")
        subprocess.run(["git", "add", "--", ".gitattributes"], cwd=ROOT, check=True, capture_output=True)
        assert not git("diff", "--name-only", "--diff-filter=U")
        with (RUN / (name + "_resolved_commit.log")).open("xb") as output:
            subprocess.run(["git", "diff", "--cached", "--check"], cwd=ROOT, stdout=output, stderr=subprocess.STDOUT, check=True)
            subprocess.run(["git", "commit", "-m", message], cwd=ROOT, stdout=output, stderr=subprocess.STDOUT, check=True)
        item["attribute_union"] = additions
    item["integrated_sha"] = git("rev-parse", "HEAD")
    destination.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
assert user_hash == hashlib.sha256((ROOT / "frontend/tsconfig.tsbuildinfo").read_bytes()).hexdigest()
receipt["ended_at"], receipt["user_buildinfo_unchanged"] = now(), True
destination.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps({"head": git("rev-parse", "HEAD"), "packages": len(packages), "stage_accepted": False, "push": "not_run"}))
