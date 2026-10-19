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


assert git("rev-parse", "HEAD") == "48b56033cf5daf3ce8cfaa710c0acbda7cc2356e"
assert git("branch", "--show-current") == "codex/full-delivery-recovery"
assert git("remote", "get-url", "origin") == "https://github.com/Gowin-liuyin/dianziCup.git"
assert not git("diff", "--cached", "--name-only")
assert not git("status", "--porcelain", "--", "backend/src", "backend/tests", "backend/migrations", "backend/pyproject.toml", "backend/uv.lock", "frontend/src", ".gitattributes")
packages = [
    ("r10_graph_12", "ff5aa737f37c7a591bee6758485e745a0e83b086", "reports/reviews/recovery/G-C-R10-pg-evidence-graph-review-1-recheck2.md", "cdbfdb9c3a85a327169718f7e4d8ce9b70aa18fcefd8b5ceb01f9ca48028d143", "reports/runs/recovery_r10_pg_evidence_graph_review1_recheck2_20261016/reviewer_artifact_manifest.json", "8df36e1fb15f3b9c21b6912c1a6031a28fd9eca8635e4909aa6e6e4e0212f3cd", "G-C integrate reviewed current PG evidence graph 1.2"),
    ("r17_default_graph_app", "164cae93ac888180b056a4c694011402ee387383", "reports/reviews/recovery/G-E-R17-graph-app-review-1.md", "c92fc216b21fc513d1a138670bd93b1f19aa8e741f4d0d332ba6c9d6a92ba6ba", "reports/runs/recovery_r17_graph_app_review1_20261016/artifact_manifest.json", "bc9548f04afcdd9d11d2c21079819d4fd1841bb25474ba3a78d8dc7862c44c9b", "G-E integrate reviewed graph navigation into default App"),
    ("r11_r08_forward_ddl", "99fec14d1a64f9c5adaa5beb294e804da3e1d18d", "reports/reviews/recovery/G-D-R11-R08-forward-migrations-review-1.md", "ba7781ebf3a7785a8ebe7a3f3e43d2f08b893c96428e3bb894dde0a89e04958a", "reports/runs/recovery_r11_r08_forward_migrations_review1_20261016/artifact_manifest.json", "2ead6acce350e583b9818c1491a395de487b50a248b1b4df252d542b36e97d80", "G-D integrate reviewed forward inventory and aggregate migrations"),
]
receipt = {"started_at": now(), "before_sha": git("rev-parse", "HEAD"), "scope": "reviewed slices only; no stage/whole-task acceptance", "push": "not_run", "packages": []}
destination = RUN / "graph_app_migrations_integration_receipt.json"
for name, target, report, report_hash, manifest, manifest_hash, message in packages:
    assert hashlib.sha256((ROOT / report).read_bytes()).hexdigest() == report_hash
    assert hashlib.sha256((ROOT / manifest).read_bytes()).hexdigest() == manifest_hash
    argv = ["git", "merge", "--no-ff", target, "-m", message]
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
