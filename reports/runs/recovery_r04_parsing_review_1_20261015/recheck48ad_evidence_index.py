"""Freeze targeted recheck identity and prove unchanged PDF safety implementation."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

directory = Path(__file__).resolve().parent
repo = Path.cwd()


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=repo, text=True).strip()


unchanged_paths = ["backend/src/ai_intel/ingestion/parsing/_pdf_worker.py", "backend/src/ai_intel/ingestion/parsing/pdf_text.py", "backend/src/ai_intel/ingestion/parsing/text_blocks.py", "backend/src/ai_intel/knowledge/evidence.py", "backend/pyproject.toml", "backend/uv.lock", "fixtures/synthetic/pdf_image_only_test.pdf", "docs/references/competition_brief.pdf"]
comparisons = {path: {"f2_blob": git("rev-parse", "f2c5873fa8c2695ae81d673e7107ada3e9b52a81:" + path), "48ad_blob": git("rev-parse", "HEAD:" + path)} for path in unchanged_paths}
for row in comparisons.values():
    row["equal"] = row["f2_blob"] == row["48ad_blob"]
receipts = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(directory.glob("recheck48ad_*.receipt.json"))]
spec = importlib.util.spec_from_file_location("recheck_security_scan", repo / "scripts/security_scan.py")
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
findings = []
for path in sorted(directory.iterdir()):
    if path.is_file() and path.suffix in {".py", ".json", ".log"}:
        content = path.read_text(encoding="utf-8", errors="replace")
        for pattern_id, pattern in module.PATTERNS.items():
            count = len(list(pattern.finditer(content)))
            if count:
                findings.append({"file": path.name, "pattern_id": pattern_id, "count": count})
report = {"recorded_at": datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds"), "sha": git("rev-parse", "HEAD"), "tree": git("rev-parse", "HEAD^{tree}"), "backend_src_tree": git("rev-parse", "HEAD:backend/src"), "status": git("status", "--short"), "PDF_resource_and_contract_blob_comparisons": comparisons, "json_parser_sha256": hashlib.sha256((repo / "backend/src/ai_intel/ingestion/parsing/parsers.py").read_bytes()).hexdigest(), "cbm_cache": "/tmp/dianzi-cbm-r04-parsing-recheck48ad-20261015", "cbm_project": "dianzi-r04-parsing-recheck48ad", "raw_coverage_totals": json.loads((directory / "recheck48ad_coverage_raw.json").read_text())['totals'], "receipts": receipts, "review_artifact_shape_scan": {"findings": findings, "exact_secret_scan": "not_run"}}
(directory / "evidence_index_recheck48ad.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"sha": report["sha"], "tree": report["tree"], "backend_src_tree": report["backend_src_tree"], "status": report["status"], "all_PDF_resource_blobs_unchanged": all(row["equal"] for row in comparisons.values()), "raw_coverage": report["raw_coverage_totals"]["percent_covered"], "receipts": len(receipts), "artifact_shape_scan": report["review_artifact_shape_scan"]}))
