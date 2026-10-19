"""Integrate two sealed slices sequentially, retaining all unexpected conflicts for review."""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
PACKAGES = (
    {
        "name": "r07_taxonomy",
        "source": "5b3869e4dcdfa16c0ae393cd73acae4cf27efbf9",
        "material": "6705303ab8eaa19d57194f1982819d25b1415d04",
        "report": "reports/reviews/recovery/G-C-R07-input-capabilities-review-1.md",
        "review_commit": "6d640a014c8d07f628f18151c0c9be0a811f03b9",
        "manifest": "reports/runs/recovery_r07_input_review1_20261016/review_manifest.json",
        "manifest_sha256": "6ad8787f4833b310b0e01a41c036d525f0f80b1a5f2f191c5120c21b4683e22b",
        "message": "G-C integrate reviewed taxonomy and bounded evidence context validation",
    },
    {
        "name": "r12_production_0020",
        "source": "ed0e14a03a06ed104f23afd0be5407d873ed8edf",
        "material": "8c03ed305f8d40bfcaf4b090e95979e75fba7147",
        "report": "reports/reviews/recovery/G-D-R12-production-migration-review-1.md",
        "report_sha256": "89579f9db93b36a48154ef6f8f301ad0fcabe1882e855bd91cad5f06c4559edb",
        "review_commit": None,
        "manifest": "reports/runs/recovery_r12_production_review1_20261016/review_manifest.json",
        "manifest_sha256": "cb27ac0e914a48a4d49587b144b0d46b855f25d031f324e4bc4f8b8c65ac3bd6",
        "message": "G-D integrate independently reviewed forward hybrid retrieval migration 0020",
    },
)


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def now():
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def digest(relative):
    return hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()


assert git("rev-parse", "HEAD").decode().strip() == "20e26fdb454c6f84713bd650f9fece6509214fa1"
assert git("branch", "--show-current").decode().strip() == "codex/full-delivery-recovery"
assert not git("diff", "--cached", "--name-only").strip()
assert not git("status", "--porcelain", "--", "backend", "frontend/src", ".gitattributes").strip()
assert digest("frontend/tsconfig.tsbuildinfo") == "3c587edfd308fb5cf04efa6e2d87b7005ef28c8c656842059b2eca405738e43d"
receipt = {"started_at": now(), "baseline": git("rev-parse", "HEAD").decode().strip(), "packages": [], "stage_accepted": False, "whole_cards_accepted": [], "push": "not_run"}
receipt_path = RUN / "taxonomy_0020_integration_receipt.json"
for package in PACKAGES:
    assert digest(package["manifest"]) == package["manifest_sha256"]
    report_bytes = (ROOT / package["report"]).read_bytes()
    if package["review_commit"]:
        report_blob = git("show", package["review_commit"] + ":" + package["report"])
        assert report_bytes.replace(b"\r\n", b"\n") == report_blob.replace(b"\r\n", b"\n")
    else:
        assert hashlib.sha256(report_bytes).hexdigest() == package["report_sha256"]
    subprocess.run(["git", "merge-base", "--is-ancestor", package["source"], package["material"]], cwd=ROOT, check=True, capture_output=True)
    item = {**package, "started_at": now(), "before_sha": git("rev-parse", "HEAD").decode().strip(), "observed_report_raw_sha256": hashlib.sha256(report_bytes).hexdigest(), "observed_report_lf_sha256": hashlib.sha256(report_bytes.replace(b"\r\n", b"\n")).hexdigest()}
    with (RUN / (package["name"] + "_reviewed_merge.log")).open("xb") as output:
        merged = subprocess.run(["git", "merge", "--no-commit", "--no-ff", package["material"]], cwd=ROOT, stdout=output, stderr=subprocess.STDOUT, timeout=90)
    conflicts = git("diff", "--name-only", "--diff-filter=U").decode().splitlines()
    item["initial_merge_exit_code"], item["conflicts"] = merged.returncode, conflicts
    receipt["packages"].append(item)
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
    if merged.returncode:
        assert conflicts and all(path.endswith(".gitattributes") for path in conflicts), "retain unexpected source/metadata conflict"
        for relative in conflicts:
            ours, theirs = git("show", ":2:" + relative), git("show", ":3:" + relative)
            additions = [line for line in theirs.splitlines() if line and line not in ours.splitlines()]
            assert all(line.startswith(b"reports/") or relative != ".gitattributes" for line in additions)
            (ROOT / relative).write_bytes(ours.rstrip(b"\r\n") + b"\n" + b"\n".join(additions) + (b"\n" if additions else b""))
            subprocess.run(["git", "add", "--", relative], cwd=ROOT, capture_output=True, check=True)
            item.setdefault("attribute_resolutions", []).append({"path": relative, "ours_sha256": hashlib.sha256(ours).hexdigest(), "theirs_sha256": hashlib.sha256(theirs).hexdigest(), "added_exact_rules": len(additions)})
    assert not git("diff", "--name-only", "--diff-filter=U").strip()
    with (RUN / (package["name"] + "_staged_check.log")).open("xb") as output:
        checked = subprocess.run(["git", "diff", "--cached", "--check"], cwd=ROOT, stdout=output, stderr=subprocess.STDOUT)
    item["staged_check_exit_code"] = checked.returncode
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
    assert checked.returncode == 0, "preserve staged evidence failure; inspect before changing bytes"
    with (RUN / (package["name"] + "_integration_commit.log")).open("xb") as output:
        committed = subprocess.run(["git", "commit", "-m", package["message"]], cwd=ROOT, stdout=output, stderr=subprocess.STDOUT, timeout=90)
    assert committed.returncode == 0
    item.update({"ended_at": now(), "integrated_sha": git("rev-parse", "HEAD").decode().strip(), "source_conflicts": 0, "commit_exit_code": committed.returncode})
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
receipt.update({"ended_at": now(), "user_buildinfo_unchanged": digest("frontend/tsconfig.tsbuildinfo") == "3c587edfd308fb5cf04efa6e2d87b7005ef28c8c656842059b2eca405738e43d"})
assert receipt["user_buildinfo_unchanged"]
receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps({"head": git("rev-parse", "HEAD").decode().strip(), "packages": [item["name"] for item in receipt["packages"]], "source_conflicts": 0, "stage_accepted": False, "push": "not_run"}))
