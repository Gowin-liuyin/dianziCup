"""Offline fixture-input checks preserve all frozen risk oracles and real loader validation."""

import ast
import copy
import hashlib
import json
import subprocess
from pathlib import Path
from unittest.mock import Mock
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy.orm import Session
from tests.integration.test_r18_current_risk_summary_pg import STAMP
from tests.unit.test_r07_public_signals import CVE, nvd_payload
from tests.unit.test_r18_risk_expired_fixture_input import normalize_expired_fixture_input

from ai_intel.domain.access import AccessScope, Role
from ai_intel.domain.enums import FreshnessStatus
from ai_intel.domain.records import ClaimRecord
from ai_intel.domain.values import Identifier, VisibilityScope
from ai_intel.enrichment.contracts import EnrichmentContext
from ai_intel.enrichment.inputs import (
    EnrichmentInputError,
    _explicit_cve_ids,
    _load_document,
    load_event_enrichment_inputs,
)
from ai_intel.enrichment.signals import enrich_structured_fields
from ai_intel.infrastructure.content_store import ContentStore
from ai_intel.ingestion.parsing.parsers import parse_json_document
from ai_intel.ingestion.source_catalog import CATALOG_SOURCES

ROOT = Path(__file__).resolve().parents[3]
CASE_PATH = ROOT / "backend/tests/integration/test_r18_current_risk_summary_pg.py"
BASELINE = "3260fd44389c22d744e375cc2fcea23d2340952d"


def frozen_ast():
    result = subprocess.run(
        [
            "git",
            "show",
            BASELINE + ":backend/tests/integration/test_r18_current_risk_summary_pg.py",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return ast.parse(result.stdout)


def candidate_ast():
    source = normalize_expired_fixture_input(CASE_PATH.read_text(encoding="utf-8"))
    source = source.replace(
        "VALUES (:id,:name,'structured_vulnerability',",
        "VALUES (:id,'Synthetic CVSS source','structured_vulnerability',",
        1,
    ).replace('                "name": "Synthetic CVSS source " + source_id,\n', "", 1)
    return ast.parse(source)


def test_all_original_eleven_pg_case_bodies_and_assertions_are_identical():
    original = {
        node.name: ast.dump(node, include_attributes=False)
        for node in frozen_ast().body
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
    }
    current = {
        node.name: ast.dump(node, include_attributes=False)
        for node in candidate_ast().body
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
    }
    assert len(original) == 11 and current == original


def test_only_exact_source_input_deltas_are_allowed_outside_the_new_source_helper():
    candidate = copy.deepcopy(candidate_ast())
    removals = {"helper": 0, "import": 0, "prepare": 0, "observation": 0, "claim_observation": 0}
    kept = []
    for node in candidate.body:
        if isinstance(node, ast.FunctionDef) and node.name == "prepare_fixture_source_inputs":
            removals["helper"] += 1
        elif (
            isinstance(node, ast.ImportFrom) and node.module == "ai_intel.ingestion.source_catalog"
        ):
            assert [(item.name, item.asname) for item in node.names] == [("CATALOG_SOURCES", None)]
            removals["import"] += 1
        else:
            kept.append(node)
    candidate.body = kept
    setup = next(
        node
        for node in candidate.body
        if isinstance(node, ast.FunctionDef) and node.name == "add_source_grades"
    )
    for node in ast.walk(setup):
        if isinstance(node, ast.With):
            remaining = []
            for statement in node.body:
                if (
                    isinstance(statement, ast.Expr)
                    and isinstance(statement.value, ast.Call)
                    and isinstance(statement.value.func, ast.Name)
                    and statement.value.func.id == "prepare_fixture_source_inputs"
                ):
                    assert ast.dump(statement.value, include_attributes=False) == ast.dump(
                        ast.parse("prepare_fixture_source_inputs(session, seeded)").body[0].value,
                        include_attributes=False,
                    )
                    removals["prepare"] += 1
                else:
                    remaining.append(statement)
            node.body = remaining
        if isinstance(node, ast.Call):
            keywords = []
            for keyword in node.keywords:
                if keyword.arg == "first_observed_at":
                    assert isinstance(node.func, ast.Attribute) and node.func.attr == "values"
                    assert ast.dump(keyword.value) == ast.dump(ast.Name(id="STAMP", ctx=ast.Load()))
                    removals["observation"] += 1
                elif keyword.arg == "observed_at":
                    assert isinstance(node.func, ast.Name) and node.func.id == "ClaimRecord"
                    expected = (
                        ast.parse(
                            "next(item.observed_at for item in loaded.documents "
                            "if item.revision_id == candidate.evidence[0].revision_id)"
                        )
                        .body[0]
                        .value
                    )
                    assert ast.dump(keyword.value, include_attributes=False) == ast.dump(
                        expected, include_attributes=False
                    )
                    removals["claim_observation"] += 1
                else:
                    keywords.append(keyword)
            node.keywords = keywords
    assert removals == {name: 1 for name in removals}
    assert ast.dump(candidate, include_attributes=False) == ast.dump(
        frozen_ast(), include_attributes=False
    )


def test_new_public_owner_helper_contains_no_grade_or_assessment_write():
    helper = next(
        node
        for node in candidate_ast().body
        if isinstance(node, ast.FunctionDef) and node.name == "prepare_fixture_source_inputs"
    )
    names = {node.id for node in ast.walk(helper) if isinstance(node, ast.Name)}
    assert not names.intersection({"ClaimRecord", "claims", "assessment_results", "RuleService"})
    assert not any(
        isinstance(node, ast.Attribute) and node.attr == "publish" for node in ast.walk(helper)
    )
    encoded = [
        node.args[0]
        for node in ast.walk(helper)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "dumps"
    ]
    assert len(encoded) == 1
    assert ast.dump(encoded[0], include_attributes=False) == ast.dump(
        ast.parse('{"cve": {"id": CVE}}').body[0].value, include_attributes=False
    )


def source_rows(tmp_path, payload, *, registered=False, uri=None):
    body = json.dumps(payload).encode()
    store = ContentStore(tmp_path)
    stored = store.store_bytes(body)
    parsed = parse_json_document(body)
    source_id = CATALOG_SOURCES["nvd_ollama"].source_id if registered else str(uuid4())
    row = {
        "revision_id": str(uuid4()),
        "document_id": str(uuid4()),
        "source_id": source_id,
        "visibility": "public" if registered else "tenant",
        "tenant_id": None if registered else "fixture-risk",
        "is_current": True,
        "parse_status": "parsed",
        "canonical_uri": uri or "https://nvd.nist.gov/vuln/detail/" + CVE,
        "content_hash": stored.content_hash,
        "size_bytes": len(body),
        "kind": "advisory",
        "source_metadata": {"data_mode": "fixture", "content_coverage": "full_text"},
        "normalizer_version": "fixture-json-1",
        "first_observed_at": STAMP,
    }
    blocks = [
        {
            "block_id": str(uuid4()),
            "start_offset": block.start_offset,
            "end_offset": block.end_offset,
            "block_text": block.text,
            "text_sha256": hashlib.sha256(block.text.encode()).hexdigest(),
            "json_pointer": block.block_type.removeprefix("field:"),
            "page_number": None,
        }
        for block in parsed.blocks
    ]
    return row, blocks, store


def read_source(row, blocks, store):
    session = Mock(spec=Session)
    session.scalar.return_value = "structured_vulnerability"
    session.execute.return_value.mappings.return_value = blocks
    return _load_document(
        session, store, VisibilityScope(visibility="tenant", tenant_id="fixture-risk"), row
    )


def test_registered_owner_and_tenant_grade_are_real_strict_loaded_documents(tmp_path):
    owner_row, owner_blocks, store = source_rows(tmp_path, {"cve": {"id": CVE}}, registered=True)
    grade_row, grade_blocks, _same_store = source_rows(tmp_path, nvd_payload())
    owner = read_source(owner_row, owner_blocks, store)
    grade = read_source(grade_row, grade_blocks, store)
    session = Mock(spec=Session)
    session.scalars.return_value = [CVE]
    assert _explicit_cve_ids(session, uuid4(), (owner, grade)) == (CVE,)
    attempts = enrich_structured_fields(
        EnrichmentContext(
            event_id=uuid4(),
            expected_event_version=1,
            revision_ids=(owner.revision_id, grade.revision_id),
            external_cve_ids=(CVE,),
            rule_version="fixture-input-contract-1",
        ),
        (owner, grade),
    )
    cvss = next(attempt for attempt in attempts if attempt.dimension == "cvss")
    assert len(cvss.candidates) == 1
    assert cvss.candidates[0].value.base_score == 9.8
    assert {span.revision_id for span in cvss.candidates[0].evidence} == {grade.revision_id}
    assert owner.source_id == UUID(CATALOG_SOURCES["nvd_ollama"].source_id)
    assert grade.source_id != owner.source_id and grade.observed_at == STAMP


def test_missing_uri_is_a_distinct_failure_before_any_sql_or_object_read(tmp_path):
    row, _blocks, store = source_rows(tmp_path, {"cve": {"id": CVE}})
    row["canonical_uri"] = None
    session = Mock(spec=Session)
    store.read_verified = Mock(wraps=store.read_verified)
    with pytest.raises(EnrichmentInputError, match=r"^source_uri_unavailable$"):
        _load_document(
            session, store, VisibilityScope(visibility="tenant", tenant_id="fixture-risk"), row
        )
    session.scalar.assert_not_called()
    session.execute.assert_not_called()
    store.read_verified.assert_not_called()


def test_unknown_source_identity_cannot_verify_even_matching_cve_bytes(tmp_path):
    row, blocks, store = source_rows(tmp_path, nvd_payload())
    grade = read_source(row, blocks, store)
    session = Mock(spec=Session)
    session.scalars.return_value = [CVE]
    with pytest.raises(EnrichmentInputError, match=r"^event_identifier_unverified$"):
        _explicit_cve_ids(session, uuid4(), (grade,))


def test_registered_source_with_another_owner_is_still_unverified(tmp_path):
    row, blocks, store = source_rows(tmp_path, {"cve": {"id": "CVE-2024-99999"}}, registered=True)
    owner = read_source(row, blocks, store)
    session = Mock(spec=Session)
    session.scalars.return_value = [CVE]
    with pytest.raises(EnrichmentInputError, match=r"^event_identifier_unverified$"):
        _explicit_cve_ids(session, uuid4(), (owner,))


@pytest.mark.parametrize("freshness", ["current", "unknown"])
def test_grade_claim_uses_source_observation_and_keeps_requested_freshness(tmp_path, freshness):
    row, blocks, store = source_rows(tmp_path, nvd_payload())
    grade = read_source(row, blocks, store)
    event_id = uuid4()
    context = EnrichmentContext(
        event_id=event_id,
        expected_event_version=1,
        revision_ids=(grade.revision_id,),
        external_cve_ids=(CVE,),
        rule_version="fixture-input-contract-1",
    )
    value = (
        next(
            item for item in enrich_structured_fields(context, (grade,)) if item.dimension == "cvss"
        )
        .candidates[0]
        .value
    )
    record = ClaimRecord(
        schema_version=3,
        claim_id=Identifier(value=str(uuid4())),
        subject="event:" + str(event_id),
        predicate="cvss_signal",
        object_value=value,
        claim_status="supported",
        claim_origin="structured_source",
        condition_value="unknown",
        freshness=freshness,
        asserted_at=STAMP,
        observed_at=grade.observed_at,
        scope=VisibilityScope(visibility="tenant", tenant_id="fixture-risk"),
    )
    assert record.observed_at == grade.observed_at == STAMP
    assert record.freshness == FreshnessStatus(freshness)
    if freshness == "current":
        values = record.model_dump()
        values["observed_at"] = None
        with pytest.raises(ValidationError, match="freshness=current requires observed_at"):
            ClaimRecord.model_validate(values)


def test_whole_loader_accepts_fixture_owner_and_preserves_real_unknown_source_observation(
    tmp_path, monkeypatch
):
    grade_row, grade_blocks, store = source_rows(tmp_path, nvd_payload())
    owner_row, owner_blocks, _same_store = source_rows(
        tmp_path, {"cve": {"id": CVE}}, registered=True
    )
    grade_row["first_observed_at"] = None
    event_id = uuid4()
    session = Mock(spec=Session)
    scope = AccessScope.for_authenticated_user("fixture-user", "fixture-risk", Role.ANALYST)
    monkeypatch.setattr(
        "ai_intel.enrichment.inputs.EventRepository",
        Mock(
            return_value=Mock(
                get_source_revisions=Mock(
                    return_value=(grade_row["revision_id"], owner_row["revision_id"])
                )
            )
        ),
    )
    parents = [
        {
            "revision_id": row["revision_id"],
            "visibility": row["visibility"],
            "tenant_id": row["tenant_id"],
            "document_visibility": row["visibility"],
            "document_tenant_id": row["tenant_id"],
            "source_visibility": row["visibility"],
            "source_tenant_id": row["tenant_id"],
        }
        for row in (grade_row, owner_row)
    ]
    session.execute.side_effect = [
        Mock(
            mappings=Mock(
                return_value=Mock(
                    one=Mock(
                        return_value={
                            "status": "active",
                            "visibility": "tenant",
                            "tenant_id": "fixture-risk",
                            "business_version": 1,
                        }
                    )
                )
            )
        ),
        Mock(mappings=Mock(return_value=parents)),
        Mock(mappings=Mock(return_value=(grade_row, owner_row))),
        Mock(mappings=Mock(return_value=grade_blocks)),
        Mock(mappings=Mock(return_value=owner_blocks)),
    ]
    session.scalar.return_value = "structured_vulnerability"
    session.scalars.return_value = [CVE]
    loaded = load_event_enrichment_inputs(
        session, store, scope, event_id, "fixture-input-contract-1"
    )
    assert loaded.context.external_cve_ids == (CVE,)
    assert len(loaded.documents) == 2
    assert (
        next(
            item for item in loaded.documents if item.revision_id == UUID(grade_row["revision_id"])
        ).observed_at
        is None
    )
