"""Internal schema and table identities; public schemas and production migrations stay separate."""

import inspect

import pytest
from pydantic import ValidationError
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from ai_intel.assessment.assessment_persistence import ASSESSMENT_TABLES, assessment_results
from ai_intel.assessment.persistence_contracts import RuleSupportBinding
from ai_intel.assessment.rule_persistence import RULE_TABLES
from ai_intel.assessment.rule_service import RuleService


def test_unique_local_tables_and_tenant_execution_key():
    names = {table.name for table in (*RULE_TABLES, *ASSESSMENT_TABLES)}
    assert names == {
        "condition_rule_versions",
        "rule_support_bindings",
        "rule_leaf_reviews",
        "rule_validation_receipts",
        "assessment_results",
        "assessment_scope_watches",
    }
    ddl = str(CreateTable(assessment_results).compile(dialect=postgresql.dialect()))
    assert "asset_id, tenant_id, asset_snapshot_id" in ddl
    assert (
        "tenant_id, asset_snapshot_id, rule_id, rule_version, input_digest, policy_version" in ddl
    )


@pytest.mark.parametrize(
    "extra",
    [
        dict(necessary_condition_supported=True),
        dict(tenant_id="forged"),
        dict(policy_version="model-policy"),
    ],
)
def test_binding_cannot_submit_semantic_authority_or_scope(extra):
    with pytest.raises(ValidationError):
        RuleSupportBinding.model_validate(
            dict(node_id="leaf", claim_id="claim", evidence_id="span", **extra)
        )


def test_service_does_not_accept_request_identity_or_policy():
    constructor = inspect.signature(RuleService)
    assert tuple(constructor.parameters) == ("engine", "session_token", "content_store")
    assert "policy" not in inspect.signature(RuleService.validate).parameters
    assert "approver" not in inspect.signature(RuleService.publish).parameters
