"""Independently replay only two previously captured public bodies, without copying them."""

import hashlib
import json

from run_commands import RUN, timestamp
from test_independent_boundaries_original import attempts, document

from ai_intel.enrichment.signal_sources import PublicSignalError, select_public_signal_document

from pathlib import Path

CACHE = Path("D:/dianzi-runtime-cache/01a13a70-858c-7d92-8070-0b2693ad7fc4/r06-auxiliary-source-probes")
RECEIPT = Path("D:/dianzi/reports/runs/recovery_r06_auxiliary_source_probe_20261015/probe_receipt.json")
EXPECTED_HASHES = {
    "epss_single_cve": "c842f9164ed0c3eb350310d4ac181c2a65d61f05629f221b907ab4753d3a59e3",
    "cisa_kev_json": "47b463a136b8e0956756cfbcdbc2e4b4ccb60c96b4ca7a1ca9f507817cc83045",
}
started = timestamp()
observations = {item["name"]: item for item in json.loads(RECEIPT.read_bytes())["probes"]
                if item["name"] in EXPECTED_HASHES}
records = []
for signal, source_name in (("epss", "epss_single_cve"), ("kev", "cisa_kev_json")):
    raw = (CACHE / (source_name + ".body")).read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    original = observations[source_name]
    assert digest == EXPECTED_HASHES[source_name] == original["sha256"]
    assert original["http_status"] == 200
    wire = json.loads(raw)
    targets = ["CVE-2024-37032"] if signal == "epss" else ["CVE-2024-37032", "CVE-2026-105134"]
    rows = wire["data" if signal == "epss" else "vulnerabilities"]
    for cve in targets:
        field = "cve" if signal == "epss" else "cveID"
        originals = [(index, row) for index, row in enumerate(rows) if row[field] == cve]
        assert len(originals) <= 1
        selected = select_public_signal_document(signal, raw, cve)
        payload = json.loads(selected.payload)
        source = document(payload, selected.canonical_uri, coverage="metadata_only",
                          observed=original["ended_at"])
        attempt = attempts(source, cves=(cve,))[signal]
        assert payload["selection"]["source_response_sha256"] == digest
        assert payload["selection"]["source_total_count"] == len(rows)
        assert payload["selection"]["source_record_index"] == (originals[0][0] if originals else None)
        assert attempt.status.value == ("available" if originals else "not_found")
        if originals:
            value = attempt.candidates[0].value
            row = originals[0][1]
            assert value.cve_id == cve
            if signal == "epss":
                assert value.probability == float(row["epss"]) and value.percentile == float(row["percentile"])
                assert str(value.data_date) == row["date"] and value.model_version is None
            else:
                assert value.required_action == row["requiredAction"] and str(value.date_added) == row["dateAdded"]
                assert value.catalog_version == wire["catalogVersion"]
            for evidence in attempt.candidates[0].evidence:
                block = next(item for item in source.blocks if item.block_id == evidence.block_id)
                assert block.text[evidence.start_offset:evidence.end_offset] == evidence.quote_text
                assert evidence.quote_sha256 == hashlib.sha256(evidence.quote_text.encode()).hexdigest()
        else:
            assert not attempt.candidates and attempt.searched_at is not None
        records.append({"signal": signal, "cve_id": cve, "source_body_sha256": digest,
                        "source_bytes": len(raw), "source_record_count": len(rows),
                        "selection_bytes": len(selected.payload), "status": attempt.status.value,
                        "candidate_count": len(attempt.candidates),
                        "evidence_count": sum(len(candidate.evidence) for candidate in attempt.candidates),
                        "exact_quote_check": "passed", "model_version": None if signal == "epss" else "not_applicable"})
    corrupt = json.loads(raw)
    if signal == "epss":
        corrupt["data"][0]["cve"] = "CVE-2024-99999"
        expected_error = "cross_cve_epss_lookup"
    else:
        corrupt["vulnerabilities"][0]["requiredAction"] = ""
        expected_error = "invalid_kev_record"
    try:
        select_public_signal_document(signal, json.dumps(corrupt).encode(), "CVE-2024-37032")
    except PublicSignalError as error:
        assert error.code == expected_error
        records.append({"signal": signal, "synthetic_mutation_of_recorded_body": True,
                        "expected_error": expected_error, "actual_error": error.code, "status": "passed"})
    else:
        raise AssertionError("Malformed recorded response was accepted")
result = {"started_at": started, "ended_at": timestamp(), "verification_layer": "recorded_response_contract",
          "live": "not_run", "new_network_calls": 0, "new_model_calls": 0, "pg_calls": 0,
          "copied_raw_bodies": False, "records": records}
(RUN / "recorded_public_replay.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, indent=2))
