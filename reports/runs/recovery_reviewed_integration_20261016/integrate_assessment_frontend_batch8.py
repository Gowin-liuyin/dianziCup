"""Import the independently rechecked UI and its required frozen serialized PG example."""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
AUTHOR = Path("C:/Users/yinha/.codex/worktrees/r17-assessment-label-fix1/dianzi")
SOURCE = "3076816126f78403e30d4539366253bf83c0cbf5"
MATERIAL = "2f55c41b806b904eb38550abb03a7dd945e10b96"


def git(directory, *arguments):
    return subprocess.check_output(["git", *arguments], cwd=directory)


def clock():
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


started = clock()
protected = ROOT / "frontend/tsconfig.tsbuildinfo"
protected_hash = hashlib.sha256(protected.read_bytes()).hexdigest()
assert protected_hash == "3c587edfd308fb5cf04efa6e2d87b7005ef28c8c656842059b2eca405738e43d"
names = [
    "AssessmentPanel.test.tsx", "AssessmentPanel.tsx", "AssessmentWorkspace.test.tsx",
    "AssessmentWorkspace.tsx", "assessment-client.test.ts", "assessment-client.ts",
    "assessment-contracts.test.ts", "assessment-contracts.ts", "assessment-label-boundary.test.ts",
    "assessment.css", "assessment.fixture.ts",
]
paths = [(SOURCE, "frontend/src/features/assessments/" + name) for name in names]
sample = "reports/runs/recovery_r17_assessment_panel_20261016/backend_serialized_receipt_example.json"
paths.append((MATERIAL, sample))
pending = []
for commit, relative in paths:
    assert not git(ROOT, "status", "--porcelain=v1", "--", relative).strip(), relative
    target = ROOT / relative
    assert not target.exists(), relative
    raw = git(AUTHOR, "show", commit + ":" + relative)
    if relative == sample:
        canonical = raw
        raw = (AUTHOR / relative).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == "9cc7964af1bba4a8a782d9c0cd7e4f66e223b160a00d5c97f9a3064cff410771"
        assert raw.replace(b"\r\n", b"\n") == canonical
    pending.append((target, raw, {"path": relative, "source_sha": commit, "git_blob_oid": git(AUTHOR, "rev-parse", commit + ":" + relative).decode().strip(), "raw_sha256": hashlib.sha256(raw).hexdigest()}))
records = []
for target, raw, record in pending:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(raw)
    record["root_blob_oid"] = git(ROOT, "hash-object", "--path", record["path"], str(target)).decode().strip()
    if record["path"] != sample:
        assert record["root_blob_oid"] == record["git_blob_oid"]
    records.append(record)
assert hashlib.sha256(protected.read_bytes()).hexdigest() == protected_hash
receipt = {"started_at": started, "ended_at": clock(), "root_baseline_sha": git(ROOT, "rev-parse", "HEAD").decode().strip(), "records": records, "review_sha": "cc4d5064939b876e486e44d2f832d2d94d447758", "review_report_sha256": "c1715e63b05358fb6a2ecf534061f060592196eec65270027cb49c11443b6a62", "root_default_mount": "not_run", "root_validation": "not_run", "stage_gate": "not_accepted"}
(RUN / "assessment_frontend_batch8_integration.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps({"imported_paths": len(records), "required_pg_sample_verified": True, "user_buildinfo_unchanged": True}))
