"""Immutable Unicode anchors and omissions are checked without running the selector again."""

import hashlib
import json

import pytest
from pydantic import ValidationError
from tests.unit.test_r07_model_fields import context, fixture_documents

from ai_intel.domain.values import VisibilityScope
from ai_intel.enrichment.evidence_selection import select_field_evidence
from ai_intel.enrichment.job_types import (
    DocumentSnapshot,
    FieldEvidenceSelectionAudit,
    FrozenEnrichmentInputs,
    validate_input_selection,
)


def unicode_selection():
    document = fixture_documents()[0]
    text = "未送全文🙂" * 3600 + "\nAffected 产品🙂 version 1.0.\n"
    block = document.blocks[0].model_copy(
        update={"text": text, "text_sha256": hashlib.sha256(text.encode()).hexdigest()}
    )
    document = document.model_copy(update={"blocks": (block,), "json_payload": None})
    frozen = FrozenEnrichmentInputs(
        context=context((document,)),
        scope=VisibilityScope(visibility="public"),
        documents=(DocumentSnapshot.model_validate(document.model_dump()),),
        parents=(),
    )
    selection = FieldEvidenceSelectionAudit.from_selection(
        select_field_evidence((document,), "versions")
    )
    return frozen, selection


def test_actual_unicode_selection_keeps_original_ranges_and_omits_unseen_body():
    frozen, selection = unicode_selection()
    validate_input_selection(selection, frozen)
    assert selection.incomplete and len(selection.omitted_ranges) == 2
    assert selection.selected[0].start_offset == 18001
    assert selection.selected[0].start_offset != len(
        frozen.documents[0].blocks[0].text[:18001].encode()
    )
    assert "未送全文" not in selection.model_dump_json()
    assert "产品🙂" in selection.texts[1]


@pytest.mark.parametrize(
    "mutation",
    [
        "source_hash",
        "source_version",
        "byte_offset",
        "missing_omission",
        "overlap",
        "report",
        "text",
        "block_hash",
    ],
)
def test_corrupt_source_range_text_or_omission_is_rejected(mutation):
    frozen, selection = unicode_selection()
    payload = selection.model_dump(mode="json")
    if mutation == "source_hash":
        payload["source_versions"][0]["content_sha256"] = "0" * 64
    elif mutation == "source_version":
        payload["source_versions"][0]["source_version"] = "invented-selector-version"
    elif mutation == "byte_offset":
        payload["selected"][0]["start_offset"] = 30001
        payload["selected"][0]["end_offset"] = 30002
    elif mutation == "missing_omission":
        payload["omitted_ranges"] = []
    elif mutation == "overlap":
        payload["selected"].append(payload["selected"][0])
        payload["texts"].append(payload["texts"][1])
    elif mutation == "report":
        report = json.loads(payload["texts"][0])
        report["selection"]["omitted_ranges"] = 0
        payload["texts"][0] = json.dumps(report)
    else:
        record = json.loads(payload["texts"][1])
        record["text" if mutation == "text" else "block_text_sha256"] = (
            "forged" if mutation == "text" else "0" * 64
        )
        payload["texts"][1] = json.dumps(record)
    with pytest.raises(ValueError):
        validate_input_selection(
            FieldEvidenceSelectionAudit.model_validate_json(json.dumps(payload)), frozen
        )


@pytest.mark.parametrize("mutation", ["bool_integer", "nested_extra", "range_extra"])
def test_selection_shape_is_strict_at_every_boundary(mutation):
    _, selection = unicode_selection()
    payload = selection.model_dump(mode="json")
    if mutation == "bool_integer":
        payload["incomplete"] = 1
    elif mutation == "nested_extra":
        payload["source_versions"][0]["tenant_id"] = "body-grant"
    else:
        payload["selected"][0]["start_offset"] = True
    with pytest.raises(ValidationError):
        FieldEvidenceSelectionAudit.model_validate_json(json.dumps(payload))
