"""Read-only runtime observations using frozen source and recorded public inputs."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REVIEW = Path(r"C:\Users\yinha\.codex\worktrees\recovery-r00-review\dianzi")
OUTPUT = Path(r"D:\dianzi\reports\runs\recovery_r00_review_1_20261014")
sys.path.insert(0, str(REVIEW / "backend/src"))

from fastapi.testclient import TestClient
from ai_intel.api.app import app
from ai_intel.ingestion.parsing.parsers import parse_pdf_text_layer
from ai_intel.ingestion.sources.nvd import normalize_nvd_record
from ai_intel.ingestion.scheduler import StreamState, FetchPageResult, commit_page_persisted
from ai_intel.infrastructure.models import clients


client = TestClient(app)
observations = {"default_app_routes": list(app.openapi()["paths"]), "auth_me_status": client.get("/auth/me").status_code,
                "ready_status": client.get("/health/ready").status_code, "ready_body": client.get("/health/ready").json()}
pdf = (REVIEW / "docs/references/competition_brief.pdf").read_bytes()
parsed = parse_pdf_text_layer(pdf)
observations["official_pdf"] = {"sha256": hashlib.sha256(pdf).hexdigest(), "parse_status": parsed.status, "notes": parsed.notes}
raw = (REVIEW / "reports/runs/plan_audit_20261014/nvd-response.json").read_bytes()
item = json.loads(raw)["vulnerabilities"][0]
try:
    observations["nvd_direct"] = {"scores": normalize_nvd_record(item).scores}
except ValueError as error:
    observations["nvd_direct"] = {"error": str(error)}
observations["nvd_wrapped_scores"] = normalize_nvd_record({"vulnerability": item}).scores
observations["nvd_recorded_score"] = item["cve"]["metrics"]["cvssMetricV31"][0]["cvssData"]["baseScore"]
state = StreamState("review1-synthetic", "live", live_cursor="original")
observations["persist_failure_count"] = commit_page_persisted(state, FetchPageResult(({"entry_id": "synthetic"},), "advanced", False), lambda item: False)
observations["persist_failure_cursor"] = state.live_cursor
observations["model_runtime_functions"] = {name: hasattr(clients, name) for name in ("generate_structured", "embed_texts", "rerank_passages")}
observations["frontend_unconnected"] = "后端 API 未连接" in (REVIEW / "frontend/src/App.tsx").read_text(encoding="utf-8")
observations["no_network_no_database"] = True
(OUTPUT / "runtime_observations.json").write_text(json.dumps(observations, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(observations, ensure_ascii=False, indent=2))
