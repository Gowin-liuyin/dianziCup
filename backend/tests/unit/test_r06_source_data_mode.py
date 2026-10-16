"""Trusted runtime mode stamps remain separate from upstream bytes and metadata."""

import json
from dataclasses import replace
from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from ai_intel.domain.access import AccessScope, Role
from ai_intel.domain.enums import DocumentKind
from ai_intel.infrastructure.content_store import ContentStore
from ai_intel.ingestion import source_jobs
from ai_intel.ingestion.catalog_documents import (
    NormalizedSourceDocument,
    _revision_metadata,
    persist_catalog_documents,
)
from ai_intel.ingestion.parsing.parsers import parse_json_document
from ai_intel.ingestion.source_documents import (
    SourceDocumentError,
    SourceResponse,
    persist_source_response,
    source_data_mode_metadata,
)

NOW = datetime(2026, 10, 16, tzinfo=UTC)
ADMIN = AccessScope.for_authenticated_user("mode-fixture-admin", None, Role.SYSTEM_ADMIN)
URL = "https://api.github.com/repos/vllm-project/vllm/security-advisories"


def paper():
    payload = json.dumps({"abstract": "Synthetic source excerpt."}).encode()
    return NormalizedSourceDocument(
        "2601.00001",
        DocumentKind.PAPER,
        "Synthetic paper",
        "https://arxiv.org/abs/2601.00001v1",
        payload,
        parse_json_document(payload),
        NOW,
        None,
        {"version_label": "v1", "full_text_fetched": False},
    )


@pytest.mark.parametrize("mode", [None, "fixture", "live"])
def test_mode_stamp_is_stable_and_unknown_has_no_truth_claim(mode):
    metadata = source_data_mode_metadata(mode)
    expected = (
        {}
        if mode is None
        else {"data_mode": mode, "data_mode_policy_version": "trusted-source-runtime-v1"}
    )
    assert metadata == expected
    assert source_data_mode_metadata(mode) == expected
    metadata["untrusted"] = True
    assert source_data_mode_metadata(mode) == expected


@pytest.mark.parametrize("mode", [None, "fixture", "live"])
def test_catalog_preserves_parser_title_and_dates_but_rejects_upstream_mode_spoof(mode):
    original = paper()
    member = replace(
        original,
        metadata={
            **original.metadata,
            "data_mode": "live",
            "data_mode_policy_version": "forged-policy",
            "title": "forged-title",
        },
    )
    metadata = _revision_metadata(member, data_mode=mode)
    assert metadata["title"] == "Synthetic paper"
    assert metadata["published_at"] == "2026-10-16T00:00:00+00:00"
    assert metadata["version_label"] == "v1"
    assert metadata["full_text_fetched"] is False
    assert metadata["parser_version"] == "json-2.0.0"
    assert metadata["normalizer_version"] == member.parsed.normalizer_version
    if mode is None:
        assert "data_mode" not in metadata and "data_mode_policy_version" not in metadata
    else:
        assert metadata["data_mode"] == mode
        assert metadata["data_mode_policy_version"] == "trusted-source-runtime-v1"
    assert member.metadata["data_mode_policy_version"] == "forged-policy"


@pytest.mark.parametrize("mode", ["", "LIVE", "unknown", True, [], {}])
def test_invalid_mode_rejected_before_gateway_or_any_persistence(tmp_path, monkeypatch, mode):
    touched = []

    def forbidden_gateway(*args, **kwargs):
        touched.append("gateway")
        raise AssertionError("invalid mode reached gateway")

    monkeypatch.setattr(source_jobs, "create_network_gateway", forbidden_gateway)
    with pytest.raises(SourceDocumentError, match="data mode"):
        source_jobs.build_source_page_handler(ContentStore(tmp_path), data_mode=mode)
    with Session() as session:
        with pytest.raises(SourceDocumentError, match="data mode"):
            persist_source_response(
                session,
                ContentStore(tmp_path),
                ADMIN,
                SourceResponse("vllm_vendor", b"[]", URL, NOW, data_mode=mode),
                ingested_at=NOW,
            )
        with pytest.raises(SourceDocumentError, match="data mode"):
            persist_catalog_documents(
                session,
                ContentStore(tmp_path),
                ADMIN,
                "arxiv_security",
                (paper(),),
                response_hash="a" * 64,
                observed_at=NOW,
                ingested_at=NOW,
                data_mode=mode,
            )
    assert touched == []
    assert list(tmp_path.rglob("*.blob")) == []
