"""Offline frozen-wire contract checks for the internal component selection seam."""

import json
from dataclasses import FrozenInstanceError
from uuid import UUID

import pytest
from tests.contract.test_public_write_adapter_contracts import validator
from tests.unit.test_public_write_adapters import fixture_receipt, fixture_request
from tests.unit.test_r18_public_component_selector import selection_fixture

from ai_intel.api.public_component_selector import select_current_component_assessments
from ai_intel.api.public_write_adapters import parse_public_stack_request, stack_current_assessments


@pytest.mark.parametrize(
    "extra", ["tenant_id", "role", "asset_id", "assessment_id", "skip_validation", "scope"]
)
def test_client_cannot_inject_selection_authority_into_frozen_component(extra):
    body = {
        "components": [
            {"ecosystem": "PyPI", "package_name": "fixture", "version": "1.0", extra: "forged"}
        ]
    }
    assert list(validator("StackCheckRequest").iter_errors(body))
    with pytest.raises(ValueError):
        parse_public_stack_request(json.dumps(body).encode())


@pytest.mark.parametrize(
    "updates", [{"version": 1}, {"component_id": None}, {"ecosystem": ""}, {"package_name": ""}]
)
def test_frozen_component_strict_fields_remain_strict(updates):
    component = {"ecosystem": "PyPI", "package_name": "fixture", "version": "1.0", **updates}
    with pytest.raises(ValueError):
        parse_public_stack_request(json.dumps({"components": [component]}).encode())


def test_internal_selection_is_immutable_and_not_added_to_public_schema():
    assessment, knowledge = selection_fixture()
    selection = select_current_component_assessments(fixture_request(), assessment, knowledge)
    with pytest.raises(FrozenInstanceError):
        selection.reason_codes = ()
    result = stack_current_assessments(
        fixture_request(), selection.assessment_ids, assessment, knowledge
    )
    validator("StackCheckResult").validate(result.model_dump(mode="json", exclude_unset=True))
    assert set(result.model_dump()) == {"kind", "results", "limitations"}


def test_optional_wire_identity_constraints_are_preserved_in_sql_candidate_selection():
    receipt = fixture_receipt()
    assessment, knowledge = selection_fixture(receipt)
    request = fixture_request(component_id=str(UUID(int=3)), purl="pkg:pypi/fixture@1.0")
    selection = select_current_component_assessments(request, assessment, knowledge)
    assert selection.assessment_ids == (UUID(receipt.assessment_id),)
    query = knowledge.session.scalars.call_args.args[0].compile()
    assert [
        {
            "ecosystem": "PyPI",
            "package_name": "fixture",
            "version": "1.0",
            "component_id": str(UUID(int=3)),
            "purl": "pkg:pypi/fixture@1.0",
        }
    ] in query.params.values()


def test_bypassed_model_copy_is_revalidated_at_selection_boundary():
    assessment, knowledge = selection_fixture()
    request = fixture_request()
    forged = request.components[0].model_copy(update={"version": 1})
    request = request.model_copy(update={"components": (forged,)})
    with pytest.raises(ValueError):
        select_current_component_assessments(request, assessment, knowledge)
    knowledge.session.scalars.assert_not_called()
