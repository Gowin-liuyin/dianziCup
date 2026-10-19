"""Merge three frozen reviewed slices while preserving unrelated working files."""

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


assert git("rev-parse", "HEAD") == "0532c4f58611e068fc7d5b03da984bc57dbad9f2"
assert git("branch", "--show-current") == "codex/full-delivery-recovery"
assert git("remote", "get-url", "origin") == "https://github.com/Gowin-liuyin/dianziCup.git"
assert not git("diff", "--cached", "--name-only")
assert not git("status", "--porcelain", "--", "backend/src", "backend/tests", "backend/migrations", "backend/pyproject.toml", "backend/uv.lock", "frontend/src", ".gitattributes")
packages = [
    ("r11_pure_sbom", "f6acedcd2b004671c317f55dd058f46e5e517de9", "reports/reviews/recovery/G-D-R11-sbom-review-1.md", "4ffa43d4d1d3a02773340cd37ed6c99efb90b8ce1f040c95817861e90084d5d3", "reports/runs/recovery_r11_sbom_review1_20261016/artifact_manifest.json", "ea25028a5f945e2c7c4efc66d7eb69d7cf8ef71ca44966b122ed58bac574b0e1", "G-D integrate reviewed pure SBOM evidence adapter"),
    ("r11_pure_conditions", "3865fd6a9c568b0d4e6b816e62eb808de5330427", "reports/reviews/recovery/G-D-R11-condition-rules-review-1.md", "dd8da52a460656e3a9a9f5a938129ee14860954a4eca9c6cf92592771ac0a7a5", "reports/runs/recovery_r11_condition_review1_20261016/review_filelist.json", "4317611410e3c667ccca08b958e6a1fa313f03dd9ea5626fd81f5f6b807d4104", "G-D integrate reviewed condition AST and rule eligibility"),
]
receipt = {"started_at": now(), "before_sha": git("rev-parse", "HEAD"), "scope": "reviewed slices only; no stage/whole-task acceptance", "push": "not_run", "packages": []}
destination = RUN / "pure_sbom_conditions_integration_receipt.json"
for name, target, report, report_hash, manifest, manifest_hash, message in packages:
    assert hashlib.sha256((ROOT / report).read_bytes()).hexdigest() == report_hash
    assert hashlib.sha256((ROOT / manifest).read_bytes()).hexdigest() == manifest_hash
    argv = ["git", "merge", "--quiet", "--no-ff", target, "-m", message]
    with (RUN / (name + "_merge.log")).open("xb") as output:
        started = now()
        result = subprocess.run(argv, cwd=ROOT, stdout=output, stderr=subprocess.STDOUT, timeout=90)
    item = {"package": name, "reviewed_material_sha": target, "review_report": report, "report_sha256": report_hash, "manifest_sha256": manifest_hash, "argv": argv, "started_at": started, "ended_at": now(), "exit_code": result.returncode}
    receipt["packages"].append(item)
    destination.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
    if result.returncode:
        unresolved = git("diff", "--name-only", "--diff-filter=U").splitlines()
        assert unresolved == [".gitattributes"], "unexpected conflict; stop for root inspection"
        ours = git("show", ":2:.gitattributes").splitlines()
        theirs = git("show", ":3:.gitattributes").splitlines()
        additions = [line for line in theirs if line not in ours]
        assert all(not line or line.startswith("reports/") for line in additions)
        assert not any(line.startswith(("<<<<<<<", "=======", ">>>>>>>")) for line in ours + additions)
        (ROOT / ".gitattributes").write_text("\n".join(ours + additions) + "\n", encoding="utf-8", newline="\n")
        subprocess.run(["git", "add", "--", ".gitattributes"], cwd=ROOT, check=True)
        assert not git("diff", "--name-only", "--diff-filter=U")
        with (RUN / (name + "_attributes_commit.log")).open("xb") as output:
            subprocess.run(["git", "diff", "--cached", "--check"], cwd=ROOT, stdout=output, stderr=subprocess.STDOUT, check=True)
            subprocess.run(["git", "commit", "-m", message], cwd=ROOT, stdout=output, stderr=subprocess.STDOUT, check=True)
        item["attribute_union"] = {"added_exact_lines": additions, "resolved_at": now()}
    item["integrated_sha"] = git("rev-parse", "HEAD")
    destination.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
receipt["ended_at"] = now()
destination.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps({"head": git("rev-parse", "HEAD"), "reviewed_slices": len(packages), "push": "not_run"}))
