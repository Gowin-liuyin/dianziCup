"""Apply only reviewed product diffs, preserving separately archived raw evidence in place."""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
BASELINE = "eebee0e5c6d39d3ace0594785b04d407353330ab"
PACKAGES = (
    ("sbom_privacy", "dcbc3d928b26f6755a5bfa71a3b70f71527bd832", "backend", "G-D-R11-integrated-api-migrations-review-1-recheck.md", "58cf83cf49af5fbe35e5b034431ffa6e7ddd3bd8c1c40cf5136cae13ac36ffe0"),
    ("sbom_frontend", "5587deb124f06b9aa14fb7feb22cdc9493ae4883", "frontend", "G-E-R17-sbom-workbench-review-1-recheck.md", "89cf702908a313736e07cd7dda4772dd3c8029b657c39d5d3f740679e3cfe0f9"),
    ("graph_projection", "707331add19f3f8eed4ba530305113028d3caedb", "backend", "G-C-R10-neo4j-projection-review-1-recheck2.md", "d7a3e3940d9a7cabc5a6cfb9d442d3c0d41d263fc2663d3cee56d3dcaed93b5d"),
    ("sdk_cli", "0601f469f1a90b9061ca77f718aa845051e76641", "sdk", "G-E-R18-sdk-cli-review-1-recheck.md", "c05810c05030c700c487815b679550060e3773fde8a7a795830a44be55afc7fe"),
)


def now():
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def git(*arguments):
    return subprocess.check_output(["git", *arguments], cwd=ROOT, timeout=300)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


assert git("rev-parse", "HEAD").decode().strip() == BASELINE
assert not git("diff", "--cached", "--name-only").strip()
assert not git("status", "--porcelain", "--", "backend", "frontend/src", "contracts", ".gitattributes").strip()
protected_path = ROOT / "frontend/tsconfig.tsbuildinfo"
protected = sha(protected_path)
assert protected == "3c587edfd308fb5cf04efa6e2d87b7005ef28c8c656842059b2eca405738e43d"
receipt = {"started_at": now(), "baseline": BASELINE, "integration_mode": "reviewed_source_only", "raw_evidence": "preserved in canonical manifests and original frozen worktrees", "whole_tasks_accepted": [], "stage_accepted": False, "push": "not_run", "packages": []}


def save():
    (RUN / "source_integration_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")


for name, target, prefix, report_name, report_sha in PACKAGES:
    report = ROOT / "reports/reviews/recovery" / report_name
    assert sha(report) == report_sha
    before = git("rev-parse", "HEAD").decode().strip()
    base = git("merge-base", before, target).decode().strip()
    files = git("diff", "--name-only", base, target, "--", prefix).decode().splitlines()
    assert files and "frontend/tsconfig.tsbuildinfo" not in files
    patch = git("diff", "--binary", base, target, "--", *files)
    (RUN / (name + "_reviewed_source.patch")).write_bytes(patch)
    item = {"name": name, "reviewed_target": target, "before": before, "base": base, "files": files, "patch_sha256": hashlib.sha256(patch).hexdigest(), "review_report": str(report.relative_to(ROOT)), "review_report_sha256": report_sha, "started_at": now()}
    receipt["packages"].append(item)
    save()
    with (RUN / (name + "_source_apply.log")).open("xb") as output:
        applied = subprocess.run(["git", "apply", "--index", "--binary", "-"], input=patch, cwd=ROOT, stdout=output, stderr=subprocess.STDOUT, timeout=120, check=False)
    item["apply_exit_code"] = applied.returncode
    save()
    assert applied.returncode == 0
    assert set(git("diff", "--cached", "--name-only").decode().splitlines()) == set(files)
    mismatches = [path for path in files if git("show", ":" + path) != git("show", target + ":" + path)]
    item["reviewed_blob_mismatches"] = mismatches
    save()
    assert not mismatches
    with (RUN / (name + "_source_staged_check.log")).open("xb") as output:
        checked = subprocess.run(["git", "diff", "--cached", "--check"], cwd=ROOT, stdout=output, stderr=subprocess.STDOUT, check=False)
    item["staged_check_exit_code"] = checked.returncode
    save()
    assert checked.returncode == 0
    with (RUN / (name + "_source_commit.log")).open("xb") as output:
        committed = subprocess.run(["git", "commit", "-m", "Recovery checkpoint integrate independently reviewed " + name.replace("_", " ")], cwd=ROOT, stdout=output, stderr=subprocess.STDOUT, timeout=300, check=False)
    item["commit_exit_code"] = committed.returncode
    save()
    assert committed.returncode == 0
    item.update(integrated_sha=git("rev-parse", "HEAD").decode().strip(), ended_at=now())
    assert sha(protected_path) == protected
    save()
    print(json.dumps({"package": name, "sha": item["integrated_sha"], "changed_files": len(files)}), flush=True)
receipt["ended_at"] = now()
save()
