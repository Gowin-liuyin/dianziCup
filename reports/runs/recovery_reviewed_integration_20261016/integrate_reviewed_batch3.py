"""Integrate reviewed source blobs and repair the omitted enrichment type dependency."""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = ROOT / "reports/runs/recovery_reviewed_integration_20261016"
PACKAGES = {
    "enrichment_type_dependency": (
        "0c57b559fe2f0d93f8a5359383f1db6cc7abc6f5",
        ["backend/src/ai_intel/enrichment/job_types.py"],
    ),
    "bounded_tool_gateway": (
        "42f26808a18c4d2b2d2f7d523f3ee0795d5b59e0",
        ["backend/src/ai_intel/investigation/tool_contracts.py",
         "backend/src/ai_intel/investigation/tool_gateway.py",
         "backend/src/ai_intel/investigation/capabilities.py"],
    ),
    "recommendation_policy": (
        "7f13f2500defbb3dae96c4aa673c8e1d7caefbba",
        ["backend/src/ai_intel/recommendations/contracts.py",
         "backend/src/ai_intel/recommendations/policy.py",
         "backend/src/ai_intel/recommendations/report_builder.py",
         "backend/tests/contract/test_r15_recommendation_contracts.py",
         "backend/tests/unit/test_r15_composite_receipt_policy.py",
         "backend/tests/unit/test_r15_recommendation_policy.py"],
    ),
    "change_candidates": (
        "2ff222797d381fc29879b9f002d07c0e66065bb6",
        ["backend/src/ai_intel/revalidation/candidate_contracts.py",
         "backend/src/ai_intel/revalidation/candidates.py",
         "backend/tests/contract/test_r16_assessment_candidate_contracts.py",
         "backend/tests/integration/test_r16_assessment_candidates_pg.py",
         "backend/tests/unit/test_r16_assessment_candidates.py"],
    ),
}


def git(*arguments: str) -> bytes:
    return subprocess.check_output(["git", *arguments], cwd=ROOT)


assert not git("diff", "--cached", "--name-only").strip()
assert git("rev-parse", "HEAD").decode().strip() == "312958e0fc54ae7a665d16c085b61660c79d9bbf"
protected = ROOT / "frontend/tsconfig.tsbuildinfo"
expected = hashlib.sha256(protected.read_bytes()).hexdigest()
assert expected == "3c587edfd308fb5cf04efa6e2d87b7005ef28c8c656842059b2eca405738e43d"
receipts = []
for name, (target, paths) in PACKAGES.items():
    if name == "bounded_tool_gateway":
        additions = git("diff", "--name-only", target + "^", target, "--", "backend/tests").decode().splitlines()
        previous = git("diff", "--name-only", "17ab90e0", target, "--", "backend/tests").decode().splitlines()
        paths = paths + [item for item in set(additions + previous) if "r14" in item]
    before = git("rev-parse", "HEAD").decode().strip()
    patch = git("diff", "--binary", before, target, "--", *paths)
    assert patch
    (RUN / ("batch3_" + name + ".patch")).write_bytes(patch)
    for action in (["git", "apply", "--check", "--index"], ["git", "apply", "--index"]):
        result = subprocess.run(action, cwd=ROOT, input=patch, capture_output=True)
        with (RUN / ("batch3_" + name + "_apply.log")).open("ab") as log:
            log.write(result.stdout + result.stderr)
        assert result.returncode == 0
    staged = git("diff", "--cached", "--name-only").decode().splitlines()
    assert set(staged) == set(paths)
    for path in paths:
        assert git("rev-parse", ":" + path).strip() == git("rev-parse", target + ":" + path).strip()
    check = subprocess.run(["git", "diff", "--cached", "--check"], cwd=ROOT, capture_output=True)
    (RUN / ("batch3_" + name + "_check.log")).write_bytes(check.stdout + check.stderr)
    assert check.returncode == 0
    result = subprocess.run(["git", "commit", "-m", "checkpoint recovery: integrate reviewed " + name], cwd=ROOT, capture_output=True)
    (RUN / ("batch3_" + name + "_commit.log")).write_bytes(result.stdout + result.stderr)
    assert result.returncode == 0
    receipts.append({"package": name, "reviewed_source": target, "before": before,
                     "after": git("rev-parse", "HEAD").decode().strip(), "files": paths,
                     "exact_reviewed_blobs": True, "exit_code": 0})
assert hashlib.sha256(protected.read_bytes()).hexdigest() == expected
receipt = {"ended_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
           "packages": receipts, "pushed": False, "phase_passed": False,
           "missing_dependency_original_exit": 2, "missing_dependency_original_collection_errors": 11}
(RUN / "batch3_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
print(json.dumps(receipt))
