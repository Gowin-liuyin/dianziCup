"""精确集成已独立复核的R15完整前置与修复，保护无关现有修改。"""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
SOURCE = "a4e3bd94d3af66a19e1fde94b0100d3faf3c3ba9"
ZONE = ZoneInfo("Asia/Shanghai")
FILES = [
    "backend/src/ai_intel/api/recommendation_routes.py",
    "backend/src/ai_intel/recommendations/candidate_loader.py",
    "backend/src/ai_intel/recommendations/mutation_receipts.py",
    "backend/src/ai_intel/recommendations/persistence_models.py",
    "backend/src/ai_intel/recommendations/service.py",
    "backend/src/ai_intel/recommendations/service_contracts.py",
    "backend/tests/contract/test_r15_http_recommendation_schema.py",
    "backend/tests/contract/test_r15_persistent_subscription_contracts.py",
    "backend/tests/integration/test_r15_http_recommendations_pg.py",
    "backend/tests/integration/test_r15_persistent_subscriptions_pg.py",
    "backend/tests/security/test_r15_http_fix1_scope.py",
    "backend/tests/security/test_r15_http_recommendation_boundaries.py",
    "backend/tests/unit/test_r15_http_recommendation_inputs.py",
    "backend/tests/unit/test_r15_persistent_subscription_rules.py",
]
started = datetime.now(ZONE).isoformat(timespec="seconds")
before = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
protected = ROOT / "frontend/tsconfig.tsbuildinfo"
protected_hash = hashlib.sha256(protected.read_bytes()).hexdigest()
review_path = Path("D:/wt/r15-http-router-review1-fix1/reports/reviews/recovery/G-E-R15-http-router-review-1-fix1.md")
assert hashlib.sha256(review_path.read_bytes()).hexdigest() == "2ca8b6b7c4f307e52c7102d0d9aa3709323044749b51779f19fb8e6ded24658a"
assert not subprocess.check_output(["git", "diff", "--cached", "--name-only"], cwd=ROOT).strip()
rows = []
for relative in FILES:
    target = ROOT / relative
    if target.exists():
        current = subprocess.check_output(["git", "show", "HEAD:" + relative], cwd=ROOT)
        if target.read_bytes().replace(b"\r\n", b"\n") != current.replace(b"\r\n", b"\n"):
            raise RuntimeError("existing modified target is protected: " + relative)
    frozen = subprocess.check_output(["git", "show", SOURCE + ":" + relative], cwd=ROOT)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(frozen)
    rows.append({"path": relative, "source_sha256": hashlib.sha256(frozen).hexdigest()})
subprocess.run(["git", "add", "--", *FILES], cwd=ROOT, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
for row in rows:
    staged = subprocess.check_output(["git", "show", ":" + row["path"]], cwd=ROOT)
    assert hashlib.sha256(staged).hexdigest() == row["source_sha256"]
result = subprocess.run(["git", "diff", "--cached", "--check"], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
(RUN / "r15_http_source_diff_check.log").write_bytes(result.stdout)
if result.returncode:
    raise RuntimeError("staged diff check failed")
commit = subprocess.run(["git", "commit", "-m", "R15 integrate reviewed persistent subscriptions reports and scoped HTTP receipts"], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
(RUN / "r15_http_source_commit.log").write_bytes(commit.stdout)
commit.check_returncode()
after = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
assert hashlib.sha256(protected.read_bytes()).hexdigest() == protected_hash
receipt = {"started_at": started, "ended_at": datetime.now(ZONE).isoformat(timespec="seconds"), "before": before, "source_sha": SOURCE, "integration_sha": after, "files": rows, "review_sha256": hashlib.sha256(review_path.read_bytes()).hexdigest(), "scope": "source only; default application and whole stage not accepted", "protected_sha256": protected_hash}
(RUN / "r15_http_source_integration.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"before": before, "source_sha": SOURCE, "integration_sha": after, "file_count": len(rows), "protected_sha256": protected_hash}, ensure_ascii=True))
