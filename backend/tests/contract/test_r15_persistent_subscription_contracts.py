"""Internal contracts and PostgreSQL DDL shape; no public/API security pass implied."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import ForeignKeyConstraint, UniqueConstraint
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from ai_intel.recommendations.persistence_models import (
    R15_TABLES,
    r15_generations,
    r15_recommendations,
    r15_reports,
)
from ai_intel.recommendations.policy import generate_recommendation_candidates
from ai_intel.recommendations.service_contracts import (
    GenerationContent,
    PreparedGeneration,
    SubscriptionRecord,
    SubscriptionSpec,
    canonical_json_bytes,
    content_sha256,
)


def prepared_payload():
    return dict(
        subscription_id=str(uuid4()),
        subscription_version=1,
        subscription_sha256="a" * 64,
        actor_user_id="fixture-user",
        actor_tenant_id="fixture-tenant",
        actor_role="analyst",
        permission_version=1,
        cutoff_at="2026-10-16T00:00:00Z",
        event_ids=[],
        max_candidates=200,
        scope_epochs={"public": None},
        input_sha256="b" * 64,
        existing_keys=[],
    )


def test_prepared_receipt_json_roundtrip_and_utc_cutoff():
    receipt = PreparedGeneration.model_validate(prepared_payload())
    assert receipt.cutoff_at == datetime(2026, 10, 16, tzinfo=UTC)
    assert (
        PreparedGeneration.model_validate_json(
            canonical_json_bytes(receipt.model_dump(mode="json"))
        )
        == receipt
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("max_candidates", True),
        ("max_candidates", 0),
        ("max_candidates", -1),
        ("max_candidates", 201),
        ("subscription_version", True),
        ("cutoff_at", "2026-10-16T00:00:00"),
        ("cutoff_at", "2026-10-16T08:00:00+08:00"),
        ("session_token", "body-token"),
    ],
)
def test_prepared_bounds_and_no_raw_credentials(field, value):
    values = prepared_payload()
    values[field] = value
    if field == "cutoff_at" and value == "2026-10-16T08:00:00+08:00":
        receipt = PreparedGeneration.model_validate(values)
        assert receipt.cutoff_at == datetime(2026, 10, 16, tzinfo=UTC)
        assert receipt.model_dump(mode="json")["cutoff_at"].endswith("Z")
        return
    with pytest.raises(ValidationError):
        PreparedGeneration.model_validate(values)


def test_four_exact_table_names_and_pg_json_owner_constraints():
    assert [table.name for table in R15_TABLES] == [
        "r15_subscriptions",
        "r15_generations",
        "r15_recommendations",
        "r15_reports",
    ]
    for table in R15_TABLES:
        ddl = str(CreateTable(table).compile(dialect=postgresql.dialect()))
        assert "JSONB" in ddl and "tenant_id" in ddl and "user_id" in ddl
    unique_columns = {
        tuple(column.name for column in constraint.columns)
        for constraint in r15_generations.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert ("id", "subscription_id", "tenant_id", "user_id") in unique_columns
    for table in (r15_recommendations, r15_reports):
        owner_fks = [
            constraint
            for constraint in table.constraints
            if isinstance(constraint, ForeignKeyConstraint)
            and tuple(column.name for column in constraint.columns)
            == ("generation_id", "subscription_id", "tenant_id", "user_id")
        ]
        assert len(owner_fks) == 1
        assert [element.target_fullname for element in owner_fks[0].elements] == [
            "r15_generations.id",
            "r15_generations.subscription_id",
            "r15_generations.tenant_id",
            "r15_generations.user_id",
        ]


@pytest.mark.parametrize(
    "spec", [{"product_keys": ["a"]}, {"asset_ids": [str(uuid4())]}, {"risk_topics": ["AML.T0051"]}]
)
def test_subscriptions_are_explicit_server_interest_inputs(spec):
    record = SubscriptionSpec.model_validate(spec)
    assert SubscriptionSpec.model_validate_json(record.model_dump_json()) == record


def generation_payload():
    spec = SubscriptionSpec(product_keys=("PyPI:alpha",))
    subscription = SubscriptionRecord(
        subscription_id=uuid4(),
        tenant_id="fixture-tenant",
        user_id="fixture-user",
        version=1,
        spec=spec,
        spec_sha256=content_sha256(spec.model_dump(mode="json")),
        created_at=datetime(2026, 10, 16, tzinfo=UTC),
        updated_at=datetime(2026, 10, 16, tzinfo=UTC),
    )
    batch = generate_recommendation_candidates(
        subscription.policy_subscription(), (), cutoff_at=subscription.created_at
    )
    content = GenerationContent(
        subscription=subscription,
        batch=batch,
        report_batch=batch,
        gaps=(),
        event_ids=(),
        scope_epochs={"public": None},
        input_sha256="b" * 64,
        material_versions={},
        partial=False,
        data_mode="fixture",
    )
    return content.model_dump(mode="json")


@pytest.mark.parametrize(
    "malformed",
    [
        "cross_owner_batch",
        "epoch_bool",
        "unknown_material_event",
        "invalid_material_hash",
        "duplicate_roster",
    ],
)
def test_generation_canonical_contract_rejects_inconsistent_envelopes(malformed):
    payload = generation_payload()
    event_id = str(uuid4())
    if malformed == "cross_owner_batch":
        payload["report_batch"]["subscription"]["user_id"] = "other-user"
    elif malformed == "epoch_bool":
        payload["scope_epochs"]["public"] = True
    elif malformed == "unknown_material_event":
        payload["material_versions"][event_id] = "a" * 64
    elif malformed == "invalid_material_hash":
        payload["event_ids"] = [event_id]
        payload["material_versions"][event_id] = "not-a-digest"
    else:
        payload["event_ids"] = [event_id, event_id]
    with pytest.raises(ValidationError):
        GenerationContent.model_validate(payload)


def test_generation_json_roundtrip_is_finite_canonical_and_explicit_fixture():
    content = GenerationContent.model_validate(generation_payload())
    frozen = canonical_json_bytes(content.model_dump(mode="json"))
    assert (
        canonical_json_bytes(GenerationContent.model_validate_json(frozen).model_dump(mode="json"))
        == frozen
    )
    assert content.data_mode == "fixture" and content.gaps == ()
