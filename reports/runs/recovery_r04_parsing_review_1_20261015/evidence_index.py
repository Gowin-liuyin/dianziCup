"""Bind review results to the immutable tree and hash the allowed evidence files."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

directory = Path(__file__).resolve().parent
repo = Path.cwd()
git = lambda *args: subprocess.check_output(["git", *args], cwd=repo, text=True).strip()
receipts = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(directory.glob("*.receipt.json"))]
source_paths = ["backend/pyproject.toml", "backend/uv.lock", "backend/src/ai_intel/ingestion/parsing/parsers.py", "backend/src/ai_intel/ingestion/parsing/pdf_text.py", "backend/src/ai_intel/ingestion/parsing/_pdf_worker.py", "backend/src/ai_intel/ingestion/parsing/text_blocks.py", "backend/src/ai_intel/knowledge/evidence.py", "docs/decisions/CR-R04-R04_document_parsing.md", "docs/references/competition_brief.pdf", "fixtures/synthetic/pdf_image_only_test.pdf"]
spec = importlib.util.spec_from_file_location("review_security_scan", repo / "scripts/security_scan.py")
module = importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name] = module
spec.loader.exec_module(module)
log_findings = []
for path in sorted(directory.iterdir()):
    if path.is_file() and path.suffix in {".py", ".json", ".log"}:
        content = path.read_text(encoding="utf-8", errors="replace")
        for pattern_id, pattern in module.PATTERNS.items():
            count = len(list(pattern.finditer(content)))
            if count:
                log_findings.append({"file": path.name, "pattern_id": pattern_id, "count": count})
report = {"recorded_at": datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds"), "sha": git("rev-parse", "HEAD"), "tree": git("rev-parse", "HEAD^{tree}"), "backend_src_tree": git("rev-parse", "HEAD:backend/src"), "branch": git("branch", "--show-current"), "tracked_status": git("status", "--short"), "source_hashes": {path: hashlib.sha256((repo / path).read_bytes()).hexdigest() for path in source_paths}, "cbm_cache": "/tmp/dianzi-cbm-r04-parsing-review-1-20261015", "cbm_allowed_root": "/mnt/c/Users/yinha/.codex/worktrees/recovery-r04-parsing-review/dianzi/backend/src", "cbm_project": "dianzi-r04-parsing-review-1", "receipts": receipts, "review_artifact_shape_scan": {"findings": log_findings, "exact_secret_scan": "not_run"}}
(directory / "evidence_index.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"sha": report["sha"], "tree": report["tree"], "backend_src_tree": report["backend_src_tree"], "tracked_status": report["tracked_status"], "receipt_count": len(receipts), "review_artifact_shape_scan": report["review_artifact_shape_scan"]}, ensure_ascii=False))
