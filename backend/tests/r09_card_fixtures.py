"""显式fixture资料与共享客户端wire替身；没有外部请求或真实抽取声明。"""

import hashlib
import json
from datetime import UTC, datetime
from html import escape
from uuid import UUID, uuid5

import pytest
from pydantic import SecretStr

from ai_intel.api.document_contracts import DocumentDetailResponse, DocumentSummary
from ai_intel.api.knowledge_contracts import EvidenceResponse
from ai_intel.domain.access import AccessScope, Role
from ai_intel.domain.enums import SourceCategory
from ai_intel.infrastructure.models.generation import GenerationClient
from ai_intel.infrastructure.network import FetchResult, RequestDeadline
from ai_intel.ingestion.parsing.parsers import parse_html_document

DOCUMENT_ID = UUID("00000000-0000-4000-8000-000000000009")
REVISION_ID = UUID("00000000-0000-4000-8000-000000000019")
FIXTURE_TIME = datetime(2026, 10, 15, 12, tzinfo=UTC)
PUBLIC_SCOPE = AccessScope.for_authenticated_user("fixture-reader", "fixture-tenant", Role.VIEWER)
PAPER_TEXT = "攻击者可控制检索文档；只有开启写文件工具的助手才可能修改文件。"


def source_document(
    texts: tuple[str, ...] = (PAPER_TEXT,),
    kind: str = "paper",
    revision_id: UUID = REVISION_ID,
    revision_number: int = 1,
    **changes: object,
) -> DocumentDetailResponse:
    parsed = parse_html_document("".join(f"<p>{escape(text)}</p>" for text in texts).encode())
    summary = DocumentSummary.model_validate(
        {
            "document_id": DOCUMENT_ID,
            "source_id": UUID("00000000-0000-4000-8000-000000000029"),
            "revision_id": revision_id,
            "source_name": "Synthetic official publication fixture",
            "source_category": {
                "paper": SourceCategory.ACADEMIC_PAPER,
                "standard": SourceCategory.TECHNICAL_STANDARD,
                "policy": SourceCategory.POLICY_REGULATION,
            }[kind],
            "document_kind": kind,
            "title": "Synthetic knowledge card fixture",
            "canonical_uri": "https://example.org/synthetic-publication",
            "revision_number": revision_number,
            "is_current": revision_number == 1,
            "source_published_at": None,
            "source_modified_at": None,
            "first_observed_at": FIXTURE_TIME,
            "ingested_at": FIXTURE_TIME,
            "parse_status": "parsed",
            "content_coverage": "full_text",
            "published_at_raw": "2026-10-01",
            "published_precision": "calendar_date",
        }
    )
    evidence = tuple(
        EvidenceResponse(
            span_id=uuid5(revision_id, "span:" + block.block_id),
            revision_id=revision_id,
            block_id=uuid5(revision_id, "block:" + block.block_id),
            start_offset=block.start_offset,
            end_offset=block.end_offset,
            quote_text=block.text,
            quote_sha256=hashlib.sha256(block.text.encode()).hexdigest(),
            locator_kind="text",
            page_number=None,
            json_pointer=None,
            verified_at=FIXTURE_TIME,
            source_uri=summary.canonical_uri,
            source_published_at=None,
            source_modified_at=None,
            first_observed_at=FIXTURE_TIME,
            ingested_at=FIXTURE_TIME,
            data_mode="fixture",
        )
        for block in parsed.blocks
    )
    return DocumentDetailResponse.model_validate(
        {
            "document": summary,
            "evidence": evidence,
            "evidence_total": len(evidence),
            "next_evidence_offset": None,
            "license_identifier": None,
            "license_uri": None,
            "source_notes": ("Synthetic fixture, not a verified publication.",),
            "data_mode": "fixture",
            **changes,
        }
    )


def candidate_field(
    source: DocumentDetailResponse,
    name: str = "tool_permissions",
    value: str = "write_filesystem",
    quote: str | None = None,
    evidence_index: int = 0,
    **citation_changes: object,
) -> dict[str, object]:
    evidence = source.evidence[evidence_index]
    quote = quote or evidence.quote_text
    return {
        "field_name": name,
        "value": value,
        "citations": [
            {
                "evidence_id": str(evidence.span_id),
                "quote": quote,
                "start_offset": evidence.start_offset + max(0, evidence.quote_text.find(quote)),
                **citation_changes,
            }
        ],
    }


def prepared_client(
    monkeypatch: pytest.MonkeyPatch, output: object
) -> tuple[GenerationClient, list[dict[str, object]]]:
    client = GenerationClient(
        "deepseek_openai", "deepseek-flash", SecretStr("synthetic-r09-fixture-credential")
    )
    calls: list[dict[str, object]] = []

    def post(
        url: str,
        body: bytes,
        *,
        protocol_headers: dict[str, str],
        deadline: RequestDeadline,
    ) -> FetchResult:
        calls.append(json.loads(body))
        if isinstance(output, Exception):
            raise output
        if isinstance(output, int):
            return FetchResult(url, output, "application/json", b"")
        raw = output if isinstance(output, str) else json.dumps(output, ensure_ascii=False)
        wire = {
            "id": "synthetic-r09-call",
            "object": "chat.completion",
            "model": "deepseek-flash",
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": raw},
                }
            ],
        }
        return FetchResult(url, 200, "application/json", json.dumps(wire).encode())

    monkeypatch.setattr(client._gateway, "post_json", post)
    return client, calls
