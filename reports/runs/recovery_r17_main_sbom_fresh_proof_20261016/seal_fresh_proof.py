"""Freeze the new appendix and direct test results without touching old evidence."""
import hashlib
import json
import subprocess
import tarfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()
report = ROOT / "reports/reviews/recovery/G-E-R17-integrated-sbom-browser-review-1-fresh-main.md"
old_report = Path("D:/wt/r17-real-sbom-browser-review1/reports/reviews/recovery/G-E-R17-integrated-sbom-browser-review-1.md")
old_hash = hashlib.sha256(old_report.read_bytes()).hexdigest()
assert old_hash == "70aed583674be26ea4a26e2ac2f610ab6275193a33f6a9b37ac61434e8ba514c"
assert not subprocess.check_output(["git", "status", "--porcelain"], cwd=old_report.parents[3]).strip()
result = json.loads((RUN / "unit_main_result.json").read_text(encoding="utf8"))
counts = {key: result[key] for key in ["numPassedTests", "numFailedTests", "numPendingTests", "numTodoTests", "numFailedTestSuites"]}
assert tuple(counts.values()) == (557, 0, 0, 0, 0)
for label in ["install", "unit_main", "lint", "typecheck", "build"]:
    receipt = json.loads((RUN / (label + "_command.json")).read_text(encoding="utf8"))
    assert receipt["exit_code"] == 0 and receipt["resource_adapter"] is False and receipt["head"] == "8514ebb16fedfe026cc280b78fced993af1dc5e8"
assert not subprocess.check_output(["git", "status", "--porcelain", "--", "frontend", "backend", "docs", "progress", "contracts"], cwd=ROOT).strip()
assert hashlib.sha256(Path("D:/dianzi/frontend/tsconfig.tsbuildinfo").read_bytes()).hexdigest() == "3c587edfd308fb5cf04efa6e2d87b7005ef28c8c656842059b2eca405738e43d"
(RUN / "report_raw.md").write_bytes(report.read_bytes())
exclusions = {"artifact_manifest.json", "seal_receipt.json", "evidence_exact_raw.tar.gz"}
members = [file for file in RUN.rglob("*") if file.is_file() and "__pycache__" not in file.parts and file.name not in exclusions]
archive_path = RUN / "evidence_exact_raw.tar.gz"
with tarfile.open(archive_path, "w:gz") as archive:
    for file in members:
        archive.add(file, arcname=file.relative_to(RUN).as_posix(), recursive=False)
manifest = {"members": [{"path": file.relative_to(RUN).as_posix(), "size": file.stat().st_size, "raw_sha256": hashlib.sha256(file.read_bytes()).hexdigest()} for file in members], "archive_sha256": hashlib.sha256(archive_path.read_bytes()).hexdigest(), "report_raw_sha256": hashlib.sha256(report.read_bytes()).hexdigest()}
with tarfile.open(archive_path) as archive:
    for member in manifest["members"]:
        raw = archive.extractfile(member["path"]).read()
        assert len(raw) == member["size"] and hashlib.sha256(raw).hexdigest() == member["raw_sha256"]
(RUN / "artifact_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf8")
receipt = {"started_at": started, "ended_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(), "exit_code": 0, "reviewed_head": "8514ebb16fedfe026cc280b78fced993af1dc5e8", "unit_counts": counts, "resource_adapter": False, "member_count": len(members), "old_report_raw_sha256_unchanged": old_hash, "old_review_worktree_clean": True, "protected_workspace_diff_empty": True, "main_buildinfo_sha256": "3c587edfd308fb5cf04efa6e2d87b7005ef28c8c656842059b2eca405738e43d", "report_raw_sha256": manifest["report_raw_sha256"]}
(RUN / "seal_receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf8")
print(json.dumps(receipt))
