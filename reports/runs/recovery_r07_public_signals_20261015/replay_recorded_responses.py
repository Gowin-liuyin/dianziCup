"""Read prior public bytes outside Git; emit only bounded factual replay evidence, never live claims."""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from ai_intel.enrichment.contracts import EnrichmentBlock, EnrichmentContext, EnrichmentDocument
from ai_intel.enrichment.signal_sources import select_public_signal_document
from ai_intel.enrichment.signals import enrich_structured_fields
from ai_intel.ingestion.parsing.parsers import parse_json_document

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
CACHE = Path("D:/dianzi-runtime-cache/01a13a70-858c-7d92-8070-0b2693ad7fc4/r06-auxiliary-source-probes")
SOURCE_RECEIPT = Path("D:/dianzi/reports/runs/recovery_r06_auxiliary_source_probe_20261015/probe_receipt.json")


def make_document(body: bytes, uri: str, observed_at: str | None) -> EnrichmentDocument:
    parsed = parse_json_document(body)
    digest = hashlib.sha256(body).hexdigest()
    return EnrichmentDocument(
        revision_id=uuid5(NAMESPACE_URL, "r07-replay-revision:" + digest),
        document_id=uuid5(NAMESPACE_URL, "r07-replay-document:" + uri),
        source_id=uuid5(NAMESPACE_URL, "r07-replay-source:" + uri),
        document_kind="advisory", source_category="structured_vulnerability",
        canonical_uri=uri, source_record_id="recorded-contract-replay",
        content_sha256=digest, json_payload=body, observed_at=observed_at,
        blocks=tuple(EnrichmentBlock(
            block_id=uuid5(NAMESPACE_URL, digest + ":" + str(block.ordinal)),
            start_offset=block.start_offset, text=block.text,
            text_sha256=hashlib.sha256(block.text.encode()).hexdigest(),
            json_pointer=block.block_type.removeprefix("field:"),
        ) for block in parsed.blocks), blocks_complete=True, content_coverage="metadata_only",
    )


if __name__ == "__main__":
    started = datetime.now().astimezone().isoformat(timespec="seconds")
    prior = json.loads(SOURCE_RECEIPT.read_bytes())
    observations = {record["name"]: record for record in prior["probes"]}
    records = []
    for signal, filename in (("epss", "epss_single_cve.body"), ("kev", "cisa_kev_json.body")):
        raw = (CACHE / filename).read_bytes()
        receipt = observations[filename.removesuffix(".body")]
        assert receipt["sha256"] == hashlib.sha256(raw).hexdigest() and receipt["http_status"] == 200
        targets = ["CVE-2024-37032"]
        if signal == "kev":
            targets.append(json.loads(raw)["vulnerabilities"][0]["cveID"])
        for cve in targets:
            selected = select_public_signal_document(signal, raw, cve)
            document = make_document(selected.payload, selected.canonical_uri, receipt["ended_at"])
            context = EnrichmentContext(event_id=uuid5(NAMESPACE_URL, "r07-recorded-event:" + cve),
                expected_event_version=1, revision_ids=(document.revision_id,), external_cve_ids=(cve,),
                rule_version="r07-public-signals-recorded-contract")
            attempt = next(item for item in enrich_structured_fields(context, (document,)) if item.dimension == signal)
            assert attempt.status.value == ("available" if json.loads(selected.payload)["selection"]["source_record_index"] is not None else "not_found")
            records.append({"signal": signal, "cve_id": cve, "source_bytes": len(raw),
                            "source_sha256": hashlib.sha256(raw).hexdigest(),
                            "selection_bytes": len(selected.payload), "status": attempt.status.value,
                            "source_total_count": json.loads(selected.payload)["selection"]["source_total_count"],
                            "candidate_count": len(attempt.candidates),
                            "evidence_count": sum(len(candidate.evidence) for candidate in attempt.candidates),
                            "model_version": None if signal == "epss" else "not_applicable"})
    nvd_page = json.loads((ROOT / "fixtures/recorded/nvd_api_20261015_public.json").read_bytes())
    raw = json.dumps(nvd_page["vulnerabilities"][0], ensure_ascii=False).encode()
    cve = nvd_page["vulnerabilities"][0]["cve"]["id"]
    document = make_document(raw, "https://nvd.nist.gov/vuln/detail/" + cve, None)
    context = EnrichmentContext(event_id=uuid5(NAMESPACE_URL, "r07-recorded-nvd:" + cve), expected_event_version=1,
        revision_ids=(document.revision_id,), external_cve_ids=(cve,), rule_version="r07-public-signals-recorded-contract")
    attempts = {attempt.dimension: attempt for attempt in enrich_structured_fields(context, (document,))}
    assert attempts["cvss"].status.value == "available" and attempts["cwe"].status.value == "blocked"
    records.append({"signal": "nvd_cvss_cwe", "cve_id": cve, "source_bytes": len(raw),
                    "source_sha256": hashlib.sha256(raw).hexdigest(), "cvss_status": "available",
                    "cvss_evidence_count": len(attempts["cvss"].candidates[0].evidence),
                    "cwe_status": "blocked", "cwe_error": attempts["cwe"].error_code,
                    "scored_at": None, "observed_at": None})
    result = {"verification_layer": "recorded_response_contract", "product_ingestion": False,
              "new_network_calls": 0, "new_model_calls": 0, "started_at": started,
              "ended_at": datetime.now().astimezone().isoformat(timespec="seconds"),
              "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "records": records}
    (RUN / "recorded_response_receipt.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
