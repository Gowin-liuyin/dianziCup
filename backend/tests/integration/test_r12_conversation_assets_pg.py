"""Reuse real inventory snapshots; no four-state assessment or external model is inferred."""

import json
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy.orm import Session
from tests.r12_conversation_fixtures import context_identity as context_identity
from tests.r12_conversation_fixtures import conversation_database as conversation_database

from ai_intel.answering.conversation_context import ConversationContextService
from ai_intel.api.question_contracts import QuestionRequest
from ai_intel.assets.inventory import InventoryService
from ai_intel.domain.access import CrossTenantAccessError, Role

pytestmark = pytest.mark.real_pg


def import_snapshot(engine, scope, *, asset_id=None, version="1.0"):
    with Session(engine) as session, session.begin():
        return InventoryService(session, scope).import_manifest(
            json.dumps(
                {
                    "format_version": 1,
                    "components": [
                        {
                            "ecosystem": "pypi",
                            "package_name": "synthetic-package",
                            "version": version,
                        }
                    ],
                }
            ).encode(),
            manifest_format="json_manifest_v1",
            display_name="Synthetic context asset",
            source_version="synthetic-1",
            observed_at=datetime.now(UTC) - timedelta(minutes=1),
            idempotency_key=uuid4().hex,
            asset_id=asset_id,
        )


def test_pg_context_pins_snapshot_and_later_change_is_an_explicit_gap(context_identity):
    engine, _auth, _scope, _token, login = context_identity
    scope, token = login(role=Role.TENANT_ADMIN)
    first = import_snapshot(engine, scope)
    service = ConversationContextService(engine)
    turn = service.admit(
        QuestionRequest(
            question="Synthetic asset impact", asset_ids=(UUID(first.asset_id),), mode="library"
        ),
        scope,
        "asset-context",
        conversation_version=None,
        session_token=token,
    )
    assert turn.context.asset_snapshot_refs[0].snapshot_id == UUID(first.snapshot.snapshot_id)
    assert turn.context.asset_snapshot_refs[0].snapshot_sha256 == first.snapshot.snapshot_sha256
    second = import_snapshot(engine, scope, asset_id=first.asset_id, version="1.1")
    assert second.snapshot.snapshot_id != first.snapshot.snapshot_id
    result = service.read_bundle(scope, turn.turn_id, session_token=token, data_mode="fixture")
    assert result.partial
    assert {"asset_snapshot_changed", "assessment_not_configured"} <= {
        gap.reason_code for gap in result.gaps
    }
    assert result.paths == ()


def test_pg_foreign_asset_cannot_be_pinned(context_identity):
    engine, _auth, scope, token, login = context_identity
    other_scope, _other_token = login(tenant="tenant-b", role=Role.TENANT_ADMIN)
    foreign = import_snapshot(engine, other_scope)
    with pytest.raises(CrossTenantAccessError):
        ConversationContextService(engine).admit(
            QuestionRequest(
                question="Probe asset", asset_ids=(UUID(foreign.asset_id),), mode="library"
            ),
            scope,
            "foreign-asset",
            conversation_version=None,
            session_token=token,
        )
