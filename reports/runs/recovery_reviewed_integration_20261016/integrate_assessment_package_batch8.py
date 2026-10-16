"""Import exact reviewed source blobs without changing shared entry points or user files."""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
BASELINE = "1315194a8ee421b7f1131a901221f31f4cacb536"


def git(directory, *arguments):
    return subprocess.check_output(["git", *arguments], cwd=directory)


def clock():
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


started = clock()
assert git(ROOT, "rev-parse", "HEAD").decode().strip() == BASELINE
assert not git(ROOT, "diff", "--cached", "--name-only").strip()
protected = ROOT / "frontend/tsconfig.tsbuildinfo"
protected_hash = hashlib.sha256(protected.read_bytes()).hexdigest()
assert protected_hash == "3c587edfd308fb5cf04efa6e2d87b7005ef28c8c656842059b2eca405738e43d"
packages = [
    (
        Path("D:/wt/r11-assessment-http-entry"),
        "48ad1d15acc51112fc09329490ae50f7dea68735",
        "D:/wt/r11-assessment-http-review-1/reports/reviews/recovery/G-D-R11-assessment-http-review-1.md",
        [
            "backend/src/ai_intel/assessment/http_contracts.py",
            "backend/src/ai_intel/assessment/http_routes.py",
            "backend/tests/contract/test_r11_assessment_http_contracts.py",
            "backend/tests/integration/test_r11_assessment_http_pg.py",
            "backend/tests/r11_assessment_http_fixtures.py",
            "backend/tests/unit/test_r11_assessment_http_routes.py",
        ],
    ),
    (
        Path("C:/Users/yinha/.codex/worktrees/r18-installable-package/dianzi"),
        "1460e020e16e83b1ee9b0e2c1e4beab2fa79ea9b",
        "C:/Users/yinha/.codex/worktrees/r18-package-review1/dianzi/reports/reviews/recovery/G-E-R18-installable-package-review-1.md",
        [
            "sdk/python/LICENSE",
            "sdk/python/MANIFEST.in",
            "sdk/python/README.md",
            "sdk/python/pyproject.toml",
            "sdk/python/tests/test_package_distribution.py",
        ],
    ),
]
pending = []
for directory, source, review, paths in packages:
    assert Path(review).is_file()
    for relative in paths:
        assert not git(ROOT, "status", "--porcelain=v1", "--", relative).strip(), relative
        raw = git(directory, "show", source + ":" + relative)
        target = ROOT / relative
        record = {
            "path": relative,
            "source_sha": source,
            "source_blob_oid": git(directory, "rev-parse", source + ":" + relative).decode().strip(),
            "canonical_sha256": hashlib.sha256(raw).hexdigest(),
            "review_ref": review,
            "before_sha256": hashlib.sha256(target.read_bytes()).hexdigest() if target.exists() else None,
        }
        pending.append((target, raw, record))
records = []
for target, raw, record in pending:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(raw)
    assert git(ROOT, "hash-object", "--path", record["path"], str(target)).decode().strip() == record["source_blob_oid"]
    records.append(record)
assert hashlib.sha256(protected.read_bytes()).hexdigest() == protected_hash
receipt = {
    "started_at": started,
    "ended_at": clock(),
    "baseline_sha": BASELINE,
    "records": records,
    "protected_buildinfo_sha256": protected_hash,
    "default_assessment_mount": "not_run",
    "root_package_build": "not_run",
    "root_validation": "not_run",
    "stage_gate": "not_accepted",
}
(RUN / "assessment_package_batch8_integration.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps({"imported_exact_blobs": len(records), "protected_user_file_unchanged": True}))
