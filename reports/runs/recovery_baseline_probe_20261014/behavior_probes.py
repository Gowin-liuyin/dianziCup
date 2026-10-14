"""Read-only recovery baseline probes; no product or secret files are written."""

from __future__ import annotations

import hashlib
import inspect
import json
from pathlib import Path

from fastapi.testclient import TestClient

from ai_intel.api.app import app, create_application
from ai_intel.api.authentication import (
    AuthenticationSessionService,
    InMemoryUserDirectory,
    SessionExpiredError,
)
from ai_intel.domain.access import Role
from ai_intel.infrastructure.models import clients
from ai_intel.ingestion.parsing.parsers import parse_pdf_text_layer
from ai_intel.ingestion.scheduler import FetchPageResult, StreamState, commit_page_persisted
from ai_intel.ingestion.sources.nvd import normalize_nvd_record
from ai_intel.knowledge.claims import ClaimEvidence, ClaimRecord, ClaimsLedger


def main() -> None:
    """Observe known defects against the frozen baseline without claiming acceptance."""
    root = Path(__file__).resolve().parents[3]
    output_directory = Path(__file__).resolve().parent
    observations: list[dict[str, object]] = []
    client = TestClient(app)
    observations.append({
        "probe": "default_application",
        "routes": list(app.openapi()["paths"]),
        "auth_me_status": client.get("/auth/me").status_code,
        "ready_status": client.get("/health/ready").status_code,
    })
    pdf_bytes = (root / "docs/references/competition_brief.pdf").read_bytes()
    parsed_pdf = parse_pdf_text_layer(pdf_bytes)
    observations.append({
        "probe": "official_pdf_text_layer",
        "sha256": hashlib.sha256(pdf_bytes).hexdigest(),
        "status": parsed_pdf.status,
        "notes": parsed_pdf.notes,
    })
    response_bytes = (root / "reports/runs/plan_audit_20261014/nvd-response.json").read_bytes()
    item = json.loads(response_bytes)["vulnerabilities"][0]
    try:
        direct: dict[str, object] = {"scores": normalize_nvd_record(item).scores}
    except ValueError as error:
        direct = {"error": str(error)}
    observations.append({
        "probe": "recorded_official_nvd_shape",
        "recording_sha256": hashlib.sha256(response_bytes).hexdigest(),
        "live_request_this_run": False,
        "source_score": item["cve"]["metrics"]["cvssMetricV31"][0]["cvssData"]["baseScore"],
        "direct": direct,
        "manual_wrapper_scores": normalize_nvd_record({"vulnerability": item}).scores,
    })
    ledger = ClaimsLedger()
    ledger.add_claim(ClaimRecord(
        "recovery-probe", "affected_version", "1.0", "test", None,
        "recovery-test-tenant", "public", (ClaimEvidence("probe-span", "version 1.0", "explicit"),),
    ))
    observations.append({
        "probe": "claim_persistence",
        "publish_result": ledger.publish_claims("recovery-test-tenant", "probe-epoch", ["recovery-probe"]),
        "same_instance_count": len(ledger.claims),
        "new_instance_count": len(ClaimsLedger().claims),
    })
    observations.append({
        "probe": "model_runtime_provider",
        "module_functions": [name for name, value in vars(clients).items()
                             if inspect.isfunction(value) and value.__module__ == clients.__name__],
        "module_provider_classes": [name for name, value in vars(clients).items()
                                    if inspect.isclass(value) and "Provider" in name],
        "module_generate_structured_present": hasattr(clients, "generate_structured"),
        "module_embed_texts_present": hasattr(clients, "embed_texts"),
        "module_rerank_passages_present": hasattr(clients, "rerank_passages"),
    })
    source_state = StreamState("recovery-test-source", "live", live_cursor="before-page")
    count = commit_page_persisted(
        source_state,
        FetchPageResult(({"entry_id": "persist-fails"},), "after-failed-page", False),
        lambda _: False,
    )
    observations.append({
        "probe": "cursor_after_failed_persistence",
        "committed_count": count,
        "live_cursor": source_state.live_cursor,
        "quarantined_entry_ids": source_state.quarantined_entry_ids,
        "fresh_instance_cursor": StreamState("recovery-test-source", "live").live_cursor,
    })
    directory = InMemoryUserDirectory()
    first = AuthenticationSessionService(directory, ("http://localhost:5173",), False)
    first.create_precreated_user("recovery-probe-user", "Synthetic-Probe-Password-Only", "probe-tenant", Role.VIEWER)
    token, _ = first.login("recovery-probe-user", "Synthetic-Probe-Password-Only", "http://localhost:5173", "probe-client")
    first.validate_session(token)
    second = AuthenticationSessionService(directory, ("http://localhost:5173",), False)
    try:
        second.validate_session(token)
        survives_new_instance = True
    except SessionExpiredError:
        survives_new_instance = False
    observations.append({
        "probe": "authentication_state_shared",
        "session_survives_new_service_instance": survives_new_instance,
        "same_instance_audit_count": len(first.audit_events()),
        "new_instance_audit_count": len(second.audit_events()),
        "secret_values_printed": False,
    })
    injected_client = TestClient(create_application(first))
    injected_login = injected_client.post(
        "/auth/login",
        json={"username": "recovery-probe-user", "password": "Synthetic-Probe-Password-Only"},
        headers={"origin": "http://localhost:5173"},
    )
    observations.append({
        "probe": "injected_authentication_logout_write_boundary",
        "login_status": injected_login.status_code,
        "logout_without_origin_or_csrf_status": injected_client.post("/auth/logout").status_code,
    })
    frontend_files = [str(path.relative_to(root)) for path in (root / "frontend/src").rglob("*") if path.is_file()]
    observations.append({
        "probe": "frontend_runtime_surface",
        "source_files": frontend_files,
        "app_has_unconnected_message": "后端 API 未连接" in (root / "frontend/src/App.tsx").read_text(encoding="utf-8"),
    })
    output = json.dumps(observations, ensure_ascii=False, indent=2)
    (output_directory / "behavior_probes.json").write_text(output, encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
