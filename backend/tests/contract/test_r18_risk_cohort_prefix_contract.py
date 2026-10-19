"""Cohort fencing changes inputs and lock order while frozen risk oracles stay identical."""

import ast
import copy
import subprocess
from pathlib import Path
from unittest.mock import Mock
from uuid import uuid4

import pytest
from tests.contract.test_r18_current_risk_summary_contract import SCHEMA, frozen_sdk
from tests.unit.test_public_write_adapters import fixture_request
from tests.unit.test_r18_current_risk_summary import producer_fixture
from tests.unit.test_r18_risk_expired_fixture_input import normalize_expired_fixture_input

from ai_intel.api.public_risk_summary import MAX_RULE_INPUTS, build_current_stack_envelope

ROOT = Path(__file__).resolve().parents[3]
BASELINE = "52caf5e5f4b48328026964a228adeacaec2648ed"
PRODUCER = "backend/src/ai_intel/api/public_risk_summary.py"
UNIT = "backend/tests/unit/test_r18_current_risk_summary.py"
PG = "backend/tests/integration/test_r18_current_risk_summary_pg.py"
INPUT_CONTRACT = "backend/tests/contract/test_r18_risk_fixture_input_contract.py"


def source_ast(path, *, baseline=False):
    if baseline:
        result = subprocess.run(
            ["git", "show", BASELINE + ":" + path],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
        )
        return ast.parse(result.stdout)
    source = (ROOT / path).read_text(encoding="utf-8")
    if path == PG:
        source = normalize_expired_fixture_input(source)
    module = ast.parse(source)
    if path == INPUT_CONTRACT:
        module.body = [
            node
            for node in module.body
            if not (
                isinstance(node, ast.ImportFrom)
                and node.module == "tests.unit.test_r18_risk_expired_fixture_input"
            )
        ]
        candidate = function(module, "candidate_ast")
        assignment = candidate.body[0]
        assert isinstance(assignment, ast.Assign) and isinstance(assignment.value, ast.Call)
        assert (
            isinstance(assignment.value.func, ast.Name)
            and assignment.value.func.id == "normalize_expired_fixture_input"
        )
        assert len(assignment.value.args) == 1
        assignment.value = assignment.value.args[0]
    return module


def function(module, name):
    return next(
        node for node in module.body if isinstance(node, ast.FunctionDef) and node.name == name
    )


def dump(node):
    return ast.dump(node, include_attributes=False)


def test_producer_retains_frozen_grading_and_entire_final_roster_fence():
    original, current = source_ast(PRODUCER, baseline=True), source_ast(PRODUCER)
    for name in (
        "normalized_cvss_severity",
        "_validated_grade",
        "_grade_citations",
        "_current_grade_findings",
        "_current_rule_scope",
    ):
        assert dump(function(current, name)) == dump(function(original, name))
    build = copy.deepcopy(function(current, "build_current_stack_envelope"))
    prefix_assignments = [
        node
        for node in build.body
        if isinstance(node, ast.Assign)
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id == "cohort_gap"
    ]
    assert len(prefix_assignments) == 1
    assert dump(prefix_assignments[0].value) == dump(
        ast.parse("_lock_assessment_cohort(payload, knowledge_service)").body[0].value
    )
    build.body.remove(prefix_assignments[0])
    selection = next(
        node
        for node in build.body
        if isinstance(node, ast.Assign)
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id == "selection"
    )
    assert isinstance(selection.value, ast.IfExp)
    assert dump(selection.value.test) == dump(ast.parse("cohort_gap is None").body[0].value)
    selection.value = selection.value.body
    gaps = [
        node
        for node in ast.walk(build)
        if isinstance(node, ast.Assign)
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id == "gap"
        and isinstance(node.value, ast.BoolOp)
        and dump(node.value) == dump(ast.parse("cohort_gap or rule_gap").body[0].value)
    ]
    assert len(gaps) == 1
    gaps[0].value = ast.Name(id="rule_gap", ctx=ast.Load())
    assert dump(build) == dump(function(original, "build_current_stack_envelope"))


def test_old_unit_module_only_adds_explicit_cohort_inputs_to_its_fixture():
    current = copy.deepcopy(source_ast(UNIT))
    fixture = function(current, "producer_fixture")
    index = next(
        index
        for index, node in enumerate(fixture.body)
        if isinstance(node, ast.Assign)
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id == "cohort_row"
    )
    additions = fixture.body[index:-1]
    expected = ast.parse("""
cohort_row = {
    field: getattr(receipt, field)
    for field in (
        "assessment_id", "tenant_id", "asset_id", "asset_snapshot_id",
        "event_id", "rule_id", "rule_version",
    )
}
cohort_row["result_payload"] = receipt.model_dump(mode="json")
monkeypatch.setattr(
    "ai_intel.api.public_risk_summary._assessment_cohort",
    lambda payload, knowledge: (cohort_row,),
)
monkeypatch.setattr(
    "ai_intel.api.public_risk_summary._cohort_parent_refs",
    lambda rows, knowledge: tuple(
        (item.source_id, item.document_id, item.revision_id, item.content_sha256)
        for item in receipt.prepared.inputs.sources
    ),
)
""").body
    assert [dump(node) for node in additions] == [dump(node) for node in expected]
    fixture.body[index:-1] = []
    assert dump(current) == dump(source_ast(UNIT, baseline=True))


def test_pg_name_uniqueness_is_the_only_new_input_delta_and_all_eleven_are_frozen():
    candidate = copy.deepcopy(source_ast(PG))
    original = source_ast(PG, baseline=True)
    expected_cases = {
        node.name: dump(node)
        for node in original.body
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
    }
    assert len(expected_cases) == 11
    assert {
        node.name: dump(node)
        for node in candidate.body
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
    } == expected_cases
    helper = function(candidate, "add_source_grades")
    sql_changes, parameter_changes = 0, 0
    for node in ast.walk(helper):
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and "VALUES (:id,:name,'structured_vulnerability'," in node.value
        ):
            node.value = node.value.replace(
                "VALUES (:id,:name,'structured_vulnerability',",
                "VALUES (:id,'Synthetic CVSS source','structured_vulnerability',",
            )
            sql_changes += 1
        if isinstance(node, ast.Dict):
            indices = [
                index
                for index, key in enumerate(node.keys)
                if isinstance(key, ast.Constant) and key.value == "name"
            ]
            for index in reversed(indices):
                assert dump(node.values[index]) == dump(
                    ast.parse('"Synthetic CVSS source " + source_id').body[0].value
                )
                del node.keys[index]
                del node.values[index]
                parameter_changes += 1
    assert (sql_changes, parameter_changes) == (1, 1)
    assert dump(candidate) == dump(original)
    identifiers = (str(uuid4()), str(uuid4()))
    assert len({"Synthetic CVSS source " + value for value in identifiers}) == 2


def test_old_input_contract_cases_are_identical_and_name_normalizer_is_exact():
    original, current = source_ast(INPUT_CONTRACT, baseline=True), source_ast(INPUT_CONTRACT)
    for node in original.body:
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            assert dump(function(current, node.name)) == dump(node)
    expected = ast.parse("""
def candidate_ast():
    source = CASE_PATH.read_text(encoding="utf-8")
    source = source.replace(
        "VALUES (:id,:name,'structured_vulnerability',",
        "VALUES (:id,'Synthetic CVSS source','structured_vulnerability',",
        1,
    ).replace('                "name": "Synthetic CVSS source " + source_id,\\n', "", 1)
    return ast.parse(source)
""").body[0]
    assert dump(function(current, "candidate_ast")) == dump(expected)


@pytest.mark.parametrize("change", ["candidates", "parents", "candidate_limit", "parent_limit"])
def test_incomplete_cohort_is_an_explicit_frozen_unknown_wire(monkeypatch, change):
    _receipt, service, knowledge = producer_fixture(monkeypatch)
    if change == "candidates":
        monkeypatch.setattr(
            "ai_intel.api.public_risk_summary._assessment_cohort", Mock(side_effect=[(), ({},)])
        )
    elif change == "candidate_limit":
        monkeypatch.setattr(
            "ai_intel.api.public_risk_summary._assessment_cohort",
            lambda *args: ({},) * (MAX_RULE_INPUTS + 1),
        )
    elif change == "parents":
        monkeypatch.setattr(
            "ai_intel.api.public_risk_summary._cohort_parent_refs",
            Mock(side_effect=[(), (("new-source", "doc", "rev", "a" * 64),)]),
        )
    else:
        monkeypatch.setattr(
            "ai_intel.api.public_risk_summary._cohort_parent_refs",
            lambda *args: (("source", "doc", "rev", "a" * 64),) * (MAX_RULE_INPUTS + 1),
        )
    envelope = build_current_stack_envelope(fixture_request(), service, knowledge)
    SCHEMA.validate(envelope.model_dump(mode="json", exclude_unset=True))
    client = frozen_sdk().StackCheckEnvelope.model_validate_json(
        envelope.model_dump_json(exclude_unset=True)
    )
    assert client.risk_summary.confirmation == "unknown"
    assert client.risk_summary.coverage == "unknown"
    assert client.risk_summary.unknown_component_indices == (0,)
    assert not client.risk_summary.findings
    service.read_in_session.assert_not_called()
