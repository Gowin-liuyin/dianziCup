"""Seal only this owned run/report and exclude caches and all warehouse originals."""

import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
REPORT = ROOT / "reports/tasks/R06-integrated-live.md"
CLOCK = ZoneInfo("Asia/Shanghai")
manifest = RUN / "artifact_manifest.json"
assert not manifest.exists()
receipt_path = RUN / "final_receipt.json"
receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
if receipt["evidence_check_scope"].endswith("supports_claim=false; no assertion of semantic support"):
    previous = receipt_path.read_bytes()
    original_path = RUN / "final_receipt_before_scope_metadata_erratum.json"
    assert not original_path.exists()
    original_path.write_bytes(previous)
    recorded = datetime.now(CLOCK).isoformat(timespec="seconds")
    receipt["evidence_check_scope"] = "saved block text offsets and quote hash; supports_claim flags are not semantic support judgments"
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (RUN / "final_receipt_scope_metadata_erratum.json").write_text(json.dumps({"recorded_at": recorded, "original_sha256": hashlib.sha256(previous).hexdigest(), "original_copy": original_path.relative_to(ROOT).as_posix(), "correction": "description still contained obsolete supports_claim=false after the check removed this invalid extra assumption; only author scope text corrected", "counts_results_or_business_changed": False}, indent=2) + "\n", encoding="utf-8")
recorded = datetime.now(CLOCK).isoformat(timespec="seconds")
paths = [path for path in RUN.rglob("*") if path.is_file() and path != manifest and "__pycache__" not in path.parts and path.suffix not in {".pyc", ".pyo"} and not any(part in {".mypy_cache", ".pytest_cache", "node_modules", ".venv", ".codebase-memory"} for part in path.parts)]
paths.append(REPORT)
artifact_files = [{"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for path in sorted(paths)]
payload = {"sealed_at": recorded, "code_sha": "1156b2ed6616e3a4297215c2893d2cbe633f5215", "worktree": "D:/wt/r06-integrated-live-1156", "scope": "owned live run scripts/raw logs/metadata and author report; no business code", "artifact_files": artifact_files, "cache_original_secret_or_holdout_contents_excluded": True, "self_hash_not_recursive": True, "review_refs": [{"path": "reports/reviews/recovery/G-C-R06-fixture-classification-review-1.md", "sha256": "d3e175f83e081a1f335cca1314660f35cdd0298a4a2ac6ea20656f5645a10e66"}, {"path": "reports/reviews/recovery/G-C-R06-fixture-classification-metadata-recheck.md", "sha256": "872109759e60dabba902034e3afcaed05c1b3b33da70d53e0aa90710cf07faac"}], "report_status": "awaiting_review; full R06/G-C partial, no accepted/push"}
manifest.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
for artifact in artifact_files:
    assert hashlib.sha256((ROOT / artifact["path"]).read_bytes()).hexdigest() == artifact["sha256"]
print(json.dumps({"manifest": str(manifest), "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(), "artifact_count": len(artifact_files), "total_bytes": sum(artifact["bytes"] for artifact in artifact_files), "report_sha256": hashlib.sha256(REPORT.read_bytes()).hexdigest(), "sealed_at": recorded}))
