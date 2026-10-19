"""Inspect actual callers and reproduce legacy helper limits without external IO."""

from __future__ import annotations

import json
import sys

from preflight_probe import CBM, PROJECT, ROOT, RUN, execute, now


if __name__ == "__main__":
    for label, name in (
        ("dimension_publish", PROJECT + ".ai_intel.enrichment.persistence.DimensionRepository.publish"),
        ("source_cvss", "_publish_cvss"),
        ("worker_entry", "build_celery_application"),
        ("quote_helper", "locate_quote"),
        ("model_generate", PROJECT + ".ai_intel.infrastructure.models.generation.GenerationClient.generate"),
        ("source_persist", "persist_source_response"),
    ):
        execute("cbm_" + label, CBM + ["trace_path", "--project", PROJECT,
            "--function-name", name, "--direction", "both", "--include-tests", "false"])
    execute("caller_search", ["rg", "-n",
            "DimensionRepository|DimensionSubmission|dimension_status_for_kind|ExtractionBatch|locate_quote|classify_relation|promote_poc_state|combine_exploit_signals",
            "backend/src", "backend/tests", "frontend/src", "-g", "*.py", "-g", "*.ts", "-g", "*.tsx"])
    execute("targeted_legacy_tests", [sys.executable, "-m", "pytest", "--no-cov", "-q",
            "backend/tests/unit/test_t19_structured_enrichment.py",
            "backend/tests/contract/test_t20_claim_extraction.py",
            "backend/tests/contract/test_t22_research_and_document_links.py",
            "backend/tests/contract/test_t23_poc_scores_impact.py",
            "backend/tests/unit/test_r02_dimension_publication_contract.py",
            "--junitxml=" + str(RUN / "targeted_legacy_tests.xml")], 90)
    sys.path.insert(0, str(ROOT / "backend/src"))
    from ai_intel.domain.enums import DocumentKind
    from ai_intel.enrichment.dimensions import dimension_status_for_kind
    from ai_intel.enrichment.extraction import locate_quote, reject_unsupported_identifiers
    observations = {
        "recorded_at": now(), "data_mode": "explicit inspection fixture; no PG/network/model",
        "canonical_kind_cvss_result": dimension_status_for_kind("cvss", DocumentKind.ADVISORY.value),
        "old_fixture_kind_cvss_result": dimension_status_for_kind("cvss_score", "vulnerability_advisory"),
        "unproven_but_syntactically_valid_cve_rejected": reject_unsupported_identifiers(["CVE-2024-12345"]),
        "repeated_quote_with_nonexistent_block": locate_quote("same line same line", "same line", "missing-block"),
    }
    assert observations["canonical_kind_cvss_result"] == "not_applicable"
    assert observations["old_fixture_kind_cvss_result"] == "available"
    assert observations["unproven_but_syntactically_valid_cve_rejected"] == []
    assert observations["repeated_quote_with_nonexistent_block"] == (True, True)
    (RUN / "legacy_helper_observations.json").write_text(json.dumps(observations, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"observations": 4, "external_calls": 0}))
    execute("final_baseline", ["git", "rev-parse", "HEAD", "HEAD:backend/src"])
