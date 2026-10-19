"""Integrate independently reviewed slices without signing their entire recovery cards."""

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
assert git("rev-parse", "HEAD") == "8a1b04d48346d8550f0326a77f003246a0ebbab5"
assert not git("diff", "--cached", "--name-only")
assert not git("status", "--porcelain", "--", "backend/src", "backend/tests", "backend/pyproject.toml", "backend/uv.lock", ".gitattributes")
packages = [
    ("knowledge-card-preparation", "b5ca278d739feac5dba9ca3e693d538a5a8d475e", "reports/reviews/recovery/G-C-R09-knowledge-cards-review-1-recheck.md", "reports/runs/recovery_r09_knowledge_cards_review_1_recheck_20261016/artifact_manifest.json", "4501d0367e881fb6cc3e9ec71acad5687ff9655cd852b511c81befce0d572f95", "G-C integrate reviewed evidence-card extraction preparation"),
    ("asset-manifest-preparation", "37e492b4e26fc5b6197b60d2494926d4181a21c3", "reports/reviews/recovery/G-D-R11-manifest-parser-review-1-recheck.md", "reports/runs/recovery_r11_manifest_parser_review1_recheck_20261016/artifact_manifest.json", "bfed9a57ffe30d34e432f7624f5d7f99967755088d53b66f046d3b98c60f1606", "G-D integrate reviewed bounded asset manifest parser"),
    ("single-model-dimension", "b05e63462f1b513eabc183d0a8d42b03196696d2", "reports/reviews/recovery/G-C-R07-single-model-dimension-review-1.md", "reports/runs/recovery_r07_single_model_dimension_review1_20261016/review_manifest.json", "28da9eb51fb412477224ca21947b2774d322dbdcb51eb0dd70a3e13c87d02741", "G-C integrate reviewed one-call model dimension extraction"),
]
receipt = {"started_at": now(), "before_sha": git("rev-parse", "HEAD"), "scope": "limited reviewed preparation slices; no stage or whole-card acceptance", "push_attempts": 0, "packages": []}
for name, target, report, manifest, expected, message in packages:
    assert hashlib.sha256((ROOT / manifest).read_bytes()).hexdigest() == expected
    report_hash = hashlib.sha256((ROOT / report).read_bytes()).hexdigest()
    argv = ["git", "merge", "--no-ff", target, "-m", message]
    started = now()
    with (RUN / (name + "_reviewed_merge.log")).open("xb") as output:
        result = subprocess.run(argv, cwd=ROOT, stdout=output, stderr=subprocess.STDOUT, timeout=120)
    item = {"package": name, "target_material_sha": target, "review_report": report, "review_report_sha256": report_hash, "review_manifest_sha256": expected, "argv": argv, "started_at": started, "ended_at": now(), "merge_exit_code": result.returncode}
    receipt["packages"].append(item)
    (RUN / "preparation_slices_integration_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    if result.returncode:
        unresolved = git("diff", "--name-only", "--diff-filter=U").splitlines()
        assert unresolved == [".gitattributes"], "unexpected conflict requires direct root investigation"
        base, ours, theirs = [git("show", f":{stage}:.gitattributes").splitlines() for stage in (1, 2, 3)]
        assert set(base) <= set(ours) and set(base) <= set(theirs)
        additions = [line for line in theirs if line not in ours]
        assert all(not line or line.startswith("reports/") for line in additions), "only exact evidence additions may be unioned"
        assert all(not line or not any(character in line for character in "?[]") for line in additions)
        (ROOT / ".gitattributes").write_text("\n".join(ours + additions) + "\n", encoding="utf-8")
        subprocess.run(["git", "add", "--", ".gitattributes"], cwd=ROOT, check=True)
        assert not git("diff", "--name-only", "--diff-filter=U")
        with (RUN / (name + "_attributes_commit.log")).open("xb") as output:
            subprocess.run(["git", "commit", "-m", message], cwd=ROOT, stdout=output, stderr=subprocess.STDOUT, check=True)
        item["attribute_union"] = {"added_exact_lines": additions, "resolved_at": now()}
    item["final_head"] = git("rev-parse", "HEAD")
    (RUN / "preparation_slices_integration_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
receipt["ended_at"] = now()
(RUN / "preparation_slices_integration_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"head": git("rev-parse", "HEAD"), "merged_components": len(packages), "push_attempts": 0}))
