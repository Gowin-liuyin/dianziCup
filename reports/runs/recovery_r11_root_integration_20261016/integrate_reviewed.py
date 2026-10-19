"""Merge independently reviewed SBOM and forward migrations without staging unrelated files."""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
PACKAGES = (
    ("sbom", "5be873ec38a41955b5a58e9762df4b866a7a9d63", "reports/reviews/recovery/G-D-R11-sbom-inventory-review-1-recheck.md", "00451e65d2001a8b916a1f2a8af5b6b4c22a891bd453ac66f4b8a92c3cac309d", "G-D integrate independently reviewed SBOM persistence and privacy boundaries"),
    ("forward", "569d8a7dc81fcea6b524b4fa172a5c7977388b93", "reports/reviews/recovery/G-D-R11-forward-migrations-review-1.md", "584b6828410e1e3c5e7592e775d5eaea935557bcb71629525130b017845658a1", "G-D integrate reviewed forward assessment and SBOM migrations 0021 and 0022"),
)


def git(*arguments):
    return subprocess.check_output(["git", *arguments], cwd=ROOT)


def now():
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def digest(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


assert git("rev-parse", "HEAD").decode().strip() == "cd91b87556dd93453537694b5090219ae4ed9b6c"
assert git("branch", "--show-current").decode().strip() == "codex/full-delivery-recovery"
assert not git("diff", "--cached", "--name-only").strip()
assert not git("status", "--porcelain", "--", "backend", "frontend/src", ".gitattributes").strip()
protected = digest("frontend/tsconfig.tsbuildinfo")
assert protected == "3c587edfd308fb5cf04efa6e2d87b7005ef28c8c656842059b2eca405738e43d"
receipt = {"started_at": now(), "baseline": git("rev-parse", "HEAD").decode().strip(), "packages": [], "whole_cards_accepted": [], "stage_accepted": False, "push": "not_run"}


def save():
    (RUN / "integration_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")


for name, target, report, expected, message in PACKAGES:
    assert digest(report) == expected
    before = git("rev-parse", "HEAD").decode().strip()
    base = git("merge-base", before, target).decode().strip()
    incoming = git("diff", "--name-only", base, target).decode().splitlines()
    item = {"name": name, "target": target, "before": before, "merge_base": base, "started_at": now(), "review_report": report, "review_report_sha256": expected}
    receipt["packages"].append(item)
    save()
    with (RUN / (name + "_merge.log")).open("xb") as output:
        merged = subprocess.run(["git", "merge", "--no-commit", "--no-ff", target], cwd=ROOT, stdout=output, stderr=subprocess.STDOUT, timeout=90)
    conflicts = git("diff", "--name-only", "--diff-filter=U").decode().splitlines()
    item.update(initial_merge_exit_code=merged.returncode, conflicts=conflicts)
    save()
    if conflicts:
        assert all(path.endswith(".gitattributes") for path in conflicts), "unexpected conflict retained for root diagnosis"
        for path in conflicts:
            ours, theirs = git("show", ":2:" + path), git("show", ":3:" + path)
            additions = [line for line in theirs.splitlines() if line and line not in ours.splitlines()]
            assert path != ".gitattributes" or all(line.startswith(b"reports/") for line in additions)
            (ROOT / path).write_bytes(ours.rstrip(b"\r\n") + b"\n" + b"\n".join(additions) + (b"\n" if additions else b""))
            subprocess.run(["git", "add", "--", path], cwd=ROOT, check=True, capture_output=True)
            item.setdefault("attribute_resolutions", []).append({"path": path, "added_exact_rules": len(additions)})
    assert not git("diff", "--name-only", "--diff-filter=U").strip()
    changed = git("diff", "--cached", "--name-only").decode().splitlines()
    assert set(changed) <= set(incoming), "merge staged a file outside the reviewed incoming diff"
    blob_mismatches = []
    for path in changed:
        if path.endswith(".gitattributes"):
            continue
        if git("show", ":" + path) != git("show", target + ":" + path):
            blob_mismatches.append(path)
    item["candidate_blob_mismatches"] = blob_mismatches
    save()
    assert not blob_mismatches, "automatic semantic merge needs further independent review"
    for label, paths in (("full", ()), ("product", ("backend", "frontend", "docs"))):
        with (RUN / (name + "_" + label + "_staged_check.log")).open("xb") as output:
            checked = subprocess.run(["git", "diff", "--cached", "--check", "--", *paths], cwd=ROOT, stdout=output, stderr=subprocess.STDOUT)
        item[label + "_staged_check_exit_code"] = checked.returncode
    save()
    assert item["full_staged_check_exit_code"] == 0, "retain evidence whitespace failures for explicit inspection"
    assert item["product_staged_check_exit_code"] == 0
    with (RUN / (name + "_commit.log")).open("xb") as output:
        committed = subprocess.run(["git", "commit", "-m", message], cwd=ROOT, stdout=output, stderr=subprocess.STDOUT, timeout=90)
    assert committed.returncode == 0
    item.update(integrated_sha=git("rev-parse", "HEAD").decode().strip(), ended_at=now(), commit_exit_code=committed.returncode)
    assert digest("frontend/tsconfig.tsbuildinfo") == protected
    save()
    print(json.dumps({"package": name, "sha": item["integrated_sha"], "changed_files": len(changed), "source_conflicts": 0}), flush=True)
receipt["ended_at"] = now()
save()
