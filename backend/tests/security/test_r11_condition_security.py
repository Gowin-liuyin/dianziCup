"""Offline adversarial inputs exercise the W06 boundary without executing supplied text."""

import pytest
from pydantic import ValidationError

from ai_intel.assessment.conditions import ConditionInputError, parse_condition_tree


def configuration_leaf(node_id="leaf"):
    return dict(
        node_id=node_id, kind="configuration_equals", field="trust_remote_code", expected=True
    )


@pytest.mark.parametrize("kind", ["eval", "shell", "sql", "url", "not", "python", "expression"])
def test_t27_c04_arbitrary_execution_or_not_predicate_is_rejected(kind):
    with pytest.raises(ValidationError):
        parse_condition_tree(
            dict(
                node_id="attack",
                kind=kind,
                expression="__import__('os').system('echo unexpected')",
                url="http://127.0.0.1/",
                sql="SELECT secret FROM credentials",
            )
        )


@pytest.mark.parametrize("extra", ["eval", "shell", "sql", "url", "tenant_id", "skip_validation"])
def test_t27_c04_execution_or_authority_fields_cannot_be_smuggled_into_a_valid_leaf(extra):
    with pytest.raises(ValidationError):
        parse_condition_tree({**configuration_leaf(), extra: "untrusted"})


@pytest.mark.parametrize("kind", ["all_of", "any_of"])
def test_t27_c04_empty_combination_is_rejected(kind):
    with pytest.raises(ValidationError):
        parse_condition_tree(dict(node_id="root", kind=kind, children=[]))


def test_t27_c04_frozen_depth_limit_accepts_eight_and_rejects_nine():
    tree = configuration_leaf()
    for depth in range(1, 8):
        tree = dict(node_id=f"depth{depth}", kind="all_of", children=[tree])
    assert parse_condition_tree(tree).node_id == "depth7"
    with pytest.raises(ConditionInputError, match="condition_budget_exceeded"):
        parse_condition_tree(dict(node_id="depth8", kind="all_of", children=[tree]))


def test_t27_c04_frozen_node_budget_accepts_64_and_rejects_65():
    children = [configuration_leaf(f"leaf{index}") for index in range(63)]
    assert (
        len(parse_condition_tree(dict(node_id="root", kind="all_of", children=children)).children)
        == 63
    )
    children[-1] = dict(node_id="extra", kind="all_of", children=[children[-1]])
    with pytest.raises(ConditionInputError, match="condition_budget_exceeded"):
        parse_condition_tree(dict(node_id="root", kind="all_of", children=children))


def test_t27_c04_cycles_repeated_node_ids_and_shared_nodes_are_rejected():
    tree = dict(node_id="root", kind="all_of", children=[])
    tree["children"].append(tree)
    with pytest.raises(ConditionInputError, match="cycle_or_shared_node"):
        parse_condition_tree(tree)
    child = configuration_leaf()
    with pytest.raises(ConditionInputError, match="cycle_or_shared_node"):
        parse_condition_tree(dict(node_id="root", kind="all_of", children=[child, child]))
    with pytest.raises(ConditionInputError, match="duplicate_node_id"):
        parse_condition_tree(dict(node_id="root", kind="all_of", children=[child, dict(child)]))


def test_duplicate_json_keys_and_non_boolean_targets_are_rejected():
    with pytest.raises(ValueError, match="duplicate JSON key"):
        parse_condition_tree('{"node_id":"a","kind":"all_of","kind":"eval","children":[]}')
    for value in (1, "true", None, {"eval": "True"}):
        with pytest.raises(ValidationError):
            parse_condition_tree({**configuration_leaf(), "expected": value})


@pytest.mark.parametrize(
    ("kind", "field"),
    [
        ("configuration_equals", "__dict__"),
        ("network_reachable", "http://localhost/secret"),
        ("input_channel_enabled", "file:///credentials"),
    ],
)
def test_arbitrary_field_or_url_read_is_rejected(kind, field):
    target = "channel" if kind == "input_channel_enabled" else "field"
    with pytest.raises(ValidationError):
        parse_condition_tree(dict(node_id="attack", kind=kind, **{target: field}, expected=True))
