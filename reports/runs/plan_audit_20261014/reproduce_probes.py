"""Reproduce the read-only audit observations against the current checkout."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from fastapi.testclient import TestClient

from ai_intel.api.app import app
from ai_intel.infrastructure.models import clients
from ai_intel.ingestion.parsing.parsers import parse_pdf_text_layer
from ai_intel.ingestion.scheduler import FetchPageResult, StreamState, commit_page_persisted
from ai_intel.ingestion.sources.nvd import normalize_nvd_record
from ai_intel.knowledge.claims import ClaimEvidence, ClaimRecord, ClaimsLedger


def main() -> None:
    evidence_dir = Path(__file__).resolve().parent
    project_root = evidence_dir.parents[2]
    observations: list[dict[str, object]] = []
    client = TestClient(app)
    observations.append(
        {
            "probe": "default_application",
            "routes": list(app.openapi()["paths"]),
            "auth_me_status": client.get("/auth/me").status_code,
            "ready_status": client.get("/health/ready").status_code,
        }
    )
    official_pdfs = list(project_root.glob("9*.pdf"))
    if len(official_pdfs) != 1:
        raise ValueError("Expected exactly one root-level official problem PDF")
    official_pdf = official_pdfs[0]
    pdf_bytes = official_pdf.read_bytes()
    parsed_pdf = parse_pdf_text_layer(pdf_bytes)
    observations.append(
        {
            "probe": "real_official_pdf",
            "sha256": hashlib.sha256(pdf_bytes).hexdigest(),
            "status": parsed_pdf.status,
            "notes": parsed_pdf.notes,
        }
    )
    response_bytes = (evidence_dir / "nvd-response.json").read_bytes()
    response = json.loads(response_bytes)
    item = response["vulnerabilities"][0]
    try:
        direct = {"scores": normalize_nvd_record(item).scores}
    except ValueError as error:
        direct = {"error": str(error)}
    wrapped = normalize_nvd_record({"vulnerability": item})
    observations.append(
        {
            "probe": "recorded_real_nvd_response",
            "sha256": hashlib.sha256(response_bytes).hexdigest(),
            "source_score": item["cve"]["metrics"]["cvssMetricV31"][0]["cvssData"]["baseScore"],
            "direct": direct,
            "manual_wrapper_scores": wrapped.scores,
        }
    )
    ledger = ClaimsLedger()
    ledger.add_claim(
        ClaimRecord(
            "audit-probe",
            "affected_version",
            "1.0",
            "test",
            None,
            "audit-tenant",
            "public",
            (ClaimEvidence("audit-span", "version 1.0", "explicit"),),
        )
    )
    published = ledger.publish_claims("audit-tenant", "audit-epoch", ["audit-probe"])
    observations.append(
        {
            "probe": "claim_storage",
            "publish_result": published,
            "ledger_count": len(ledger.claims),
            "new_instance_count": len(ClaimsLedger().claims),
        }
    )
    observations.append(
        {
            "probe": "real_model_entry_points",
            "generate_structured": hasattr(clients, "generate_structured"),
            "embed_texts": hasattr(clients, "embed_texts"),
            "rerank_passages": hasattr(clients, "rerank_passages"),
        }
    )
    source_state = StreamState("audit-source", "live")
    page = FetchPageResult(({"entry_id": "persist-fails"},), "after-failed-page", False)
    committed_count = commit_page_persisted(source_state, page, lambda _: False)
    observations.append(
        {
            "probe": "cursor_after_failed_persistence",
            "committed_count": committed_count,
            "live_cursor": source_state.live_cursor,
            "quarantined_entry_ids": source_state.quarantined_entry_ids,
        }
    )
    output = json.dumps(observations, ensure_ascii=False, indent=2)
    (evidence_dir / "behavior_probes_reproduced.json").write_text(output, encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
