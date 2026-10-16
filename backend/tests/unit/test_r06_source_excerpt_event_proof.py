"""Owner fields qualify exact JSON text claims without rewriting source content."""

import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from ai_intel.ingestion import source_documents
from ai_intel.ingestion.source_documents import SourceDocumentError, SourceResponse

NOW = datetime(2026, 10, 16, 10, tzinfo=UTC)
ROOT = Path(__file__).resolve().parents[3]
NVD_URL = (
    "https://services.nvd.nist.gov/rest/json/cves/2.0"
    "?keywordSearch=ollama&resultsPerPage=1&startIndex=0"
)
VENDOR_URL = (
    "https://api.github.com/repos/vllm-project/vllm/security-advisories"
    "?per_page=1&state=published&page=1"
)
ARCHIVE = ROOT / "reports/runs/recovery_r06_source_excerpt_event_proof_20261016/nvd-response.json"


def nvd_member():
    return source_documents._prepare_documents(
        SourceResponse("nvd_ollama", ARCHIVE.read_bytes(), NVD_URL, NOW)
    )[0]


def vendor_member(*, cve_id=None, description="vLLM unsafe deserialization"):
    record = json.loads((ROOT / "fixtures/recorded/vllm_vendor_20261015_public.json").read_bytes())[
        0
    ]
    record["cve_id"] = cve_id
    record["description"] = description
    return source_documents._prepare_documents(
        SourceResponse("vllm_vendor", json.dumps([record]).encode(), VENDOR_URL, NOW)
    )[0]


def submissions(monkeypatch, member, *, blocks=None, facts=None):
    captured = {}
    revision_id = str(uuid4())
    registered = {
        block.block_type.removeprefix("field:"): (str(uuid4()), block)
        for block in member.parsed.blocks
    }
    if blocks is not None:
        registered = blocks

    def attach(session, revision, start, end, pointer, quote, supported, *args, **kwargs):
        assert revision == revision_id
        assert member.parsed.normalized_text[start:end] == quote
        assert registered[pointer][0] == kwargs["block_id"]
        assert supported is True and kwargs["verified_at"] == NOW
        evidence_id = str(uuid4())
        captured[evidence_id] = (pointer, quote, revision, start, end)
        return evidence_id

    monkeypatch.setattr(source_documents, "attach_evidence_span", attach)
    with Session() as session:
        result = source_documents._fact_submissions(
            session,
            str(uuid4()),
            revision_id,
            str(uuid4()),
            member.facts if facts is None else facts,
            registered,
            NOW,
            NOW,
            member.identifier_fields,
        )
    return result, captured


def test_archived_nvd_description_has_separate_exact_owner_proof(monkeypatch):
    member = nvd_member()
    result, captured = submissions(monkeypatch, member)
    excerpt = next(item for item in result if item.record.predicate == "source_excerpt")
    proofs = [captured[link.evidence_id.value] for link in excerpt.evidence_links]
    assert [(proof[0], proof[1]) for proof in proofs] == [
        ("/cve/descriptions/0/value", excerpt.record.object_value),
        ("/cve/id", "CVE-2024-34359"),
    ]
    assert "CVE-2024-34359" not in excerpt.record.object_value
    assert member.payload in ARCHIVE.read_bytes()
    assert all(link.support_kind == "supports" for link in excerpt.evidence_links)
    assert all(link.validation_status == "validated" for link in excerpt.evidence_links)
    assert excerpt.record.schema_version == 2
    assert excerpt.record.claim_origin.value == "structured_source"
    assert len({proof[2] for proof in proofs}) == 1


@pytest.mark.parametrize("cve_id", [None, "CVE-2026-12345"])
def test_vendor_owner_ghsa_and_optional_cve_are_real_fields(monkeypatch, cve_id):
    member = vendor_member(cve_id=cve_id)
    result, captured = submissions(monkeypatch, member)
    text_claims = [item for item in result if isinstance(item.record.object_value, str)]
    for claim in text_claims:
        proofs = [captured[link.evidence_id.value][:2] for link in claim.evidence_links]
        assert proofs[0] == (claim.json_path, claim.record.object_value)
        assert proofs[1:] == [("/ghsa_id", member.record_id)] + (
            [("/cve_id", cve_id)] if cve_id is not None else []
        )


@pytest.mark.parametrize("mutation", ["wrong_cve", "reference_only", "missing_owner"])
def test_owner_mismatch_or_reference_url_is_not_qualifying_proof(monkeypatch, mutation):
    member = nvd_member()
    if mutation == "reference_only":
        payload = json.loads(ARCHIVE.read_bytes())
        payload["vulnerabilities"][0]["cve"]["references"].append(
            {"url": "https://example.invalid/CVE-2024-34359"}
        )
        member = source_documents._prepare_documents(
            SourceResponse("nvd_ollama", json.dumps(payload).encode(), NVD_URL, NOW)
        )[0]
    blocks = {
        block.block_type.removeprefix("field:"): (str(uuid4()), block)
        for block in member.parsed.blocks
    }
    owner_id, owner = blocks["/cve/id"]
    if mutation == "wrong_cve":
        blocks["/cve/id"] = (owner_id, replace(owner, text="/cve/id: CVE-2024-99999"))
    else:
        del blocks["/cve/id"]
        if mutation == "reference_only":
            assert any(
                "CVE-2024-34359" in block.text
                for pointer, (_, block) in blocks.items()
                if pointer.startswith("/cve/references/")
            )
    with pytest.raises(SourceDocumentError, match="source qualifier"):
        submissions(monkeypatch, member, blocks=blocks)


def test_unicode_bounded_excerpt_remains_exact_without_identifier_prefix(monkeypatch):
    description = "中文🙂漏洞原始条件" * 300
    member = vendor_member(description=description)
    result, captured = submissions(monkeypatch, member)
    excerpt = next(item for item in result if item.record.predicate == "source_excerpt")
    assert excerpt.record.object_value == description[:2000]
    assert captured[excerpt.evidence_links[0].evidence_id.value][1] == description[:2000]
    assert member.record_id not in excerpt.record.object_value


def test_excerpt_longer_than_original_or_changed_quote_is_rejected(monkeypatch):
    member = nvd_member()
    fact = next(fact for fact in member.facts if fact.predicate == "source_excerpt")
    for value in (fact.value + " invented continuation", "CVE-2024-34359 " + fact.value):
        with pytest.raises(SourceDocumentError, match="text fact differs"):
            submissions(monkeypatch, member, facts=(replace(fact, value=value),))


def test_legacy_cvss_qualifiers_remain_score_authority_and_vector(monkeypatch):
    result, captured = submissions(monkeypatch, nvd_member())
    for score in (item for item in result if item.record.predicate == "cvss_score"):
        paths = [captured[link.evidence_id.value][0] for link in score.evidence_links]
        metric = score.json_path.removesuffix("/cvssData/baseScore")
        assert paths == [score.json_path, metric + "/source", metric + "/cvssData/vectorString"]


def test_missing_identifier_is_rejected_without_borrowing_reference_id():
    payload = json.loads(ARCHIVE.read_bytes())
    del payload["vulnerabilities"][0]["cve"]["id"]
    with pytest.raises(SourceDocumentError):
        source_documents._prepare_documents(
            SourceResponse("nvd_ollama", json.dumps(payload).encode(), NVD_URL, NOW)
        )
