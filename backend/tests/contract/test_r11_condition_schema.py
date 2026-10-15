"""Generated internal schema parity; this does not change frozen public schemas."""

import json

import jsonschema
import pytest

from ai_intel.assessment.conditions import CONDITION_ADAPTER, parse_condition_tree

LEAVES = [
    dict(kind="component_matches", ecosystem="PyPI", package_key="fixture"),
    dict(
        kind="version_in_range",
        assertion=dict(
            package_key="fixture",
            ecosystem="PyPI",
            scheme="pep440",
            raw_expression="[0,1)",
            intervals=[dict(introduced="0", fixed="1")],
        ),
    ),
    dict(kind="configuration_equals", field="trust_remote_code", expected=True),
    dict(kind="permission_includes", permission="read"),
    dict(kind="input_channel_enabled", channel="uploaded_documents"),
    dict(kind="network_reachable", field="outbound_network_allowed"),
    dict(
        kind="inventory_proves_absence",
        ecosystem="PyPI",
        package_key="fixture",
        declared_scope="runtime",
    ),
    dict(kind="mitigation_confirmed", mitigation_key="fixture-mitigation"),
]


@pytest.mark.parametrize("payload", LEAVES)
def test_all_w06_leaf_types_roundtrip_through_internal_schema(payload):
    payload = dict(node_id="leaf", **payload)
    jsonschema.validate(payload, CONDITION_ADAPTER.json_schema())
    node = parse_condition_tree(payload)
    assert parse_condition_tree(node.model_dump_json()) == node


@pytest.mark.parametrize("kind", ["all_of", "any_of"])
def test_combinations_share_internal_schema_and_parse_boundary(kind):
    payload = dict(node_id="root", kind=kind, children=[dict(node_id="leaf", **LEAVES[0])])
    jsonschema.validate(payload, CONDITION_ADAPTER.json_schema())
    assert parse_condition_tree(payload).children[0].kind == "component_matches"


def test_schema_rejects_extra_fields_unknown_predicate_and_empty_combinations():
    for payload in (
        dict(node_id="a", kind="eval", expression="True"),
        dict(node_id="a", kind="all_of", children=[]),
        dict(node_id="a", **LEAVES[0], sql="SELECT 1"),
    ):
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(payload, CONDITION_ADAPTER.json_schema())


def test_full_ast_capacity_does_not_count_typed_version_fields_as_ast_nodes():
    children = []
    for index in range(63):
        children.append(
            dict(
                node_id=f"version{index}",
                kind="version_in_range",
                assertion=dict(
                    package_key="fixture",
                    ecosystem="PyPI",
                    scheme="pep440",
                    raw_expression="synthetic multiple source intervals",
                    intervals=[
                        dict(introduced="0", fixed="1.4.2", branch=f"branch{branch}")
                        for branch in range(50)
                    ],
                    explicit_versions=[f"1.{number}" for number in range(100)],
                ),
            )
        )
    tree = dict(node_id="root", kind="all_of", children=children)
    assert parse_condition_tree(json.dumps(tree)) == parse_condition_tree(tree)
