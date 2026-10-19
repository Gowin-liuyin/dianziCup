"""Integrate independently reviewed persistence slices with exact evidence guards."""

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
assert git("rev-parse", "HEAD") == "fcfe0c9fbe89cf5e8c64804c577c59b8d99bb30b"
assert not git("diff", "--cached", "--name-only")
assert not git("status", "--porcelain", "--", "backend/src", "backend/tests", "backend/pyproject.toml", "backend/uv.lock", ".gitattributes")
packages = [
    ("publication-provenance", "9e722c944cf83086ffd30ad24a708172c13da189", "reports/reviews/recovery/G-C-R07-publication-review-1-recheck.md", "reports/runs/recovery_r07_publication_review1_recheck_20261016/evidence_manifest.json", "e82dd5f4898b6db229933631871ef04b783ea30c505e9dd61e53d2838e098cb1", "G-C integrate reviewed atomic enrichment publication and provenance"),
    ("bulk-source-evidence", "bdebeca358f0cfd63630b223dee64647b5280687", "reports/reviews/recovery/G-C-R06-bulk-source-evidence-review-1.md", "reports/runs/recovery_r06_bulk_source_evidence_review1_20261016/artifact_manifest.json", "e6e016ec9f6144feaf95141caf34489e7449e6114b206425c2f8a951402c41e8", "G-C integrate reviewed bounded bulk source evidence persistence"),
    ("aggregate-observation-persistence", "a76374ca9200945441a83421050eceef00db47d8", "reports/reviews/recovery/G-C-R08-aggregate-persistence-review-1-recheck.md", "reports/runs/recovery_r08_aggregate_persistence_review1_recheck1_20261016/artifact_manifest.json", "f066d69eff865e71e4baa74147f6f361d2c0ef2989e5a6675bff9417742c6d27", "G-C integrate reviewed aggregate PG history and bounded cache TTL"),
    ("asset-inventory-persistence", "bc8798cf5efc81e210a429884930ca545af43ad8", "reports/reviews/recovery/G-D-R11-asset-inventory-review-1.md", "reports/runs/recovery_r11_asset_inventory_review1_20261016/artifact_manifest.json", "3c604d1e969c40d6ca37e207729ea1f7650ef61b2448f7baa87700b94c0413fb", "G-D integrate reviewed private asset inventory and immutable history"),
    ("graph-pointer-selection", "65497b14cb5c24c6d780f675a70af3ee4019d8db", "reports/reviews/recovery/G-E-R17-evidence-graph-review-1-recheck.md", "reports/runs/recovery_r17_graph_review1_recheck_20261016/artifact_manifest.json", "184e38e78839ebc53cac484d3681b5c59e68b54d4b2d2a948433fe6c58dc0b73", "G-E integrate reviewed evidence graph pointer selection"),
]
receipt = json.loads((RUN / "persistent_slices_integration_receipt.json").read_text(encoding="utf-8"))
receipt["resumed_at"] = now()
for name, target, report, manifest, expected, message in packages[1:]:
    assert hashlib.sha256((ROOT / manifest).read_bytes()).hexdigest() == expected
    report_hash = hashlib.sha256((ROOT / report).read_bytes()).hexdigest()
    argv = ["git", "merge", "--no-ff", target, "-m", message]
    with (RUN / (name + "_reviewed_merge.log")).open("xb") as output:
        started = now()
        result = subprocess.run(argv, cwd=ROOT, stdout=output, stderr=subprocess.STDOUT, timeout=120)
    item = {"package": name, "target_material_sha": target, "review_report": report, "review_report_sha256": report_hash, "review_manifest_sha256": expected, "argv": argv, "started_at": started, "ended_at": now(), "merge_exit_code": result.returncode}
    receipt["packages"].append(item)
    destination = RUN / "persistent_slices_integration_receipt.json"
    destination.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
    if result.returncode:
        unresolved = git("diff", "--name-only", "--diff-filter=U").splitlines()
        assert unresolved == [".gitattributes"], "unexpected conflict requires direct root investigation"
        base, ours, theirs = [git("show", f":{stage}:.gitattributes").splitlines() for stage in (1, 2, 3)]
        assert set(base) <= set(ours) and set(base) <= set(theirs)
        additions = [line for line in theirs if line not in ours]
        assert all(not line or line.startswith("reports/") for line in additions)
        assert all(not line or not any(character in line for character in "?[]") for line in additions)
        (ROOT / ".gitattributes").write_text("\n".join(ours + additions) + "\n", encoding="utf-8")
        subprocess.run(["git", "add", "--", ".gitattributes"], cwd=ROOT, check=True)
        assert not git("diff", "--name-only", "--diff-filter=U")
        with (RUN / (name + "_attributes_commit.log")).open("xb") as output:
            subprocess.run(["git", "diff", "--cached", "--check"], cwd=ROOT, stdout=output, stderr=subprocess.STDOUT, check=True)
            subprocess.run(["git", "commit", "-m", message], cwd=ROOT, stdout=output, stderr=subprocess.STDOUT, check=True)
        item["attribute_union"] = {"added_exact_lines": additions, "resolved_at": now()}
    item["final_head"] = git("rev-parse", "HEAD")
    destination.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
receipt["ended_at"] = now()
destination.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps({"head": git("rev-parse", "HEAD"), "merged_components": len(packages), "push_attempts": 0}))
