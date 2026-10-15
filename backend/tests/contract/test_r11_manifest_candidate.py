"""显式合成contract fixtures：保留03候选字段与来源，不改变公开schema。"""

import hashlib
import json
from dataclasses import FrozenInstanceError, asdict
from datetime import UTC, datetime

import pytest

from ai_intel.assets.manifest_parser import parse_manifest
from ai_intel.domain.access import AccessScope, Role


def test_candidate_snapshot_retains_authenticated_identity_source_and_contract_fields() -> None:
    raw = json.dumps(
        {
            "format_version": 1,
            "components": [{"package_name": "langchain", "ecosystem": "PyPI", "version": "0.2.0"}],
            "inventory_completeness": "complete_for_declared_scope",
            "declared_scope": ["fixture-declared-runtime"],
        }
    ).encode()
    result = parse_manifest(
        raw,
        manifest_format="json_manifest_v1",
        scope=AccessScope.for_authenticated_user("fixture-user", "fixture-tenant", Role.ANALYST),
        authorized_asset_tenant_id="fixture-tenant",
        asset_id="29a06008-8abf-442f-8645-a4c0f8876469",
        snapshot_number=7,
        source_version="fixture-revision-7",
        observed_at=datetime(2026, 10, 15, 12, tzinfo=UTC),
        recorded_at=datetime(2026, 10, 15, 13, tzinfo=UTC),
    )
    snapshot = result.snapshot
    assert snapshot.schema_version == "r11-asset-candidate-1"
    assert snapshot.tenant_id == "fixture-tenant"
    assert snapshot.snapshot_number == 7
    assert snapshot.observed_at.hour == 12
    assert snapshot.recorded_at.hour == 13
    assert snapshot.source_kind == "json_manifest_v1"
    assert snapshot.declared_scope == ("fixture-declared-runtime",)
    assert snapshot.inventory_completeness == "complete_for_declared_scope"
    assert result.source_sha256 == hashlib.sha256(raw).hexdigest()
    assert result.source_bytes == raw
    assert result.source_version == "fixture-revision-7"
    assert result.parser_version == "r11-manifest-parser-1"
    assert snapshot.components[0].version_scheme == "pep440"
    assert asdict(result)["source_bytes"] == raw
    assert "source_bytes" not in asdict(snapshot)
    with pytest.raises(FrozenInstanceError):
        snapshot.tenant_id = "attacker-tenant"
    with pytest.raises(FrozenInstanceError):
        snapshot.components[0].version = "future-version"
