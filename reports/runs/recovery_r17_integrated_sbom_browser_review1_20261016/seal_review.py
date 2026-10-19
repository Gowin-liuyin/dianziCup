"""Freeze independent raw evidence and remove only the temporary exact resource mount."""
import hashlib
import json
import os
import subprocess
import tarfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from sqlalchemy.engine import make_url
from offline_runner import RUN, ROOT

started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()
report = ROOT / "reports/reviews/recovery/G-E-R17-integrated-sbom-browser-review-1.md"
resource = ROOT / "reports/runs/recovery_r17_sbom_workbench_20261016/backend_contract_samples.json"
assert hashlib.sha256(resource.read_bytes()).hexdigest() == "92f5a0cac56ccd97c63af16bd14418cbc1c42cf4803c3ab6627f419235a6e331"
resolved = resource.resolve()
assert resolved.is_relative_to(ROOT.resolve()) and not resource.is_symlink()
resource.unlink()
if not list(resource.parent.iterdir()):
    resource.parent.rmdir()
assert not subprocess.check_output(["git", "status", "--porcelain", "--", "frontend", "backend", "docs", "progress", "contracts"], cwd=ROOT).strip()
captured = subprocess.run(["C:/Users/yinha/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/powershell/pwsh.exe", "-NoProfile", "-Command", "$r17Protected=Get-Content -LiteralPath 'D:/dianzi-private/test-runtime-resource-reference-20261016.dpapi' -Raw; $r17Clear=$r17Protected | ConvertTo-SecureString | ConvertFrom-SecureString -AsPlainText; [Console]::Write($r17Clear)"], capture_output=True, timeout=15, check=True)
original = make_url(json.loads(captured.stdout)["TEST_DATABASE_URL"])
sensitive = [original.password, original.render_as_string(hide_password=False), original.set(database="test_dianzi_r17_real_review1_20261016").render_as_string(hide_password=False)]
text_files = [file for file in RUN.rglob("*") if file.is_file() and file.suffix in {".json", ".log", ".md", ".xml", ".txt", ".ts", ".py", ".cjs"}]
for file in [*text_files, report]:
    value = file.read_text(encoding="utf8", errors="replace")
    assert not any(secret in value for secret in sensitive), "owned exact secret scan failed"
report_raw = report.read_bytes()
(RUN / "report_raw.md").write_bytes(report_raw)
exclusions = {"artifact_manifest.json", "evidence_exact_raw.tar.gz", "seal_receipt.json"}
members = [file for file in RUN.rglob("*") if file.is_file() and "__pycache__" not in file.parts and file.name not in exclusions]
archive_path = RUN / "evidence_exact_raw.tar.gz"
with tarfile.open(archive_path, "w:gz") as archive:
    for file in members:
        archive.add(file, arcname=file.relative_to(RUN).as_posix(), recursive=False)
manifest = {"members": [{"path": file.relative_to(RUN).as_posix(), "size": file.stat().st_size, "raw_sha256": hashlib.sha256(file.read_bytes()).hexdigest()} for file in members], "archive_sha256": hashlib.sha256(archive_path.read_bytes()).hexdigest(), "report_raw_sha256": hashlib.sha256(report_raw).hexdigest()}
with tarfile.open(archive_path) as archive:
    for member in manifest["members"]:
        raw = archive.extractfile(member["path"]).read()
        assert len(raw) == member["size"] and hashlib.sha256(raw).hexdigest() == member["raw_sha256"]
(RUN / "artifact_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf8")
receipt = {"started_at": started, "ended_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(), "exit_code": 0, "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(), "member_count": len(members), "exact_dsn_password_scan_hits": 0, "scanned_text_files": len(text_files) + 1, "temporary_resource_removed": True, "protected_workspace_diff_empty": True, "main_buildinfo_sha256": hashlib.sha256(Path("D:/dianzi/frontend/tsconfig.tsbuildinfo").read_bytes()).hexdigest(), "report_raw_sha256": manifest["report_raw_sha256"]}
assert receipt["main_buildinfo_sha256"] == "3c587edfd308fb5cf04efa6e2d87b7005ef28c8c656842059b2eca405738e43d"
(RUN / "seal_receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf8")
print(json.dumps(receipt))
