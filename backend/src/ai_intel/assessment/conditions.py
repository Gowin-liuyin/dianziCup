"""W06 pure, bounded predicates over a fixed authorized inventory and source facts."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictStr,
    TypeAdapter,
    model_validator,
)

from ai_intel.assessment.version_ranges import evaluate_version_assertion
from ai_intel.assets.inventory_contracts import AssetSnapshotResponse, DeclaredFieldResponse
from ai_intel.assets.manifest_parser import CONFIGURATION_TYPES, INPUT_CHANNELS, NETWORK_FIELDS
from ai_intel.domain.access import READ_ASSET, AccessScope
from ai_intel.domain.enrichment_values import VersionAssertionValue
from ai_intel.domain.enums import ClaimOrigin, ClaimStatus, ConditionValue
from ai_intel.domain.values import VisibilityScope
from ai_intel.infrastructure.models.json_output import strict_json_object

MAX_CONDITION_DEPTH = 8
MAX_CONDITION_NODES = 64
MAX_CONDITION_BYTES = 16 * 1024 * 1024
CONDITION_SCHEMA_VERSION: Literal["r11-condition-1"] = "r11-condition-1"
RuleKind = Literal["software_applicability", "observed_path", "research_prerequisites"]
NodeId = Annotated[str, Field(min_length=1, max_length=200, pattern=r"^[a-zA-Z0-9_.:-]+$")]
Label = Annotated[str, Field(min_length=1, max_length=200)]


class ConditionInputError(ValueError):
    """Malformed inputs are rejected with fixed reasons, never treated as negative evidence."""


class ConditionContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class ComponentMatches(ConditionContract):
    node_id: NodeId
    kind: Literal["component_matches"]
    ecosystem: Label
    package_key: Label


class VersionInRange(ConditionContract):
    node_id: NodeId
    kind: Literal["version_in_range"]
    assertion: VersionAssertionValue
    range_complete: bool = Field(default=False, strict=True)


class ConfigurationEquals(ConditionContract):
    node_id: NodeId
    kind: Literal["configuration_equals"]
    field: Literal["model_name", "provider_name", "trust_remote_code", "authentication_required"]
    expected: Annotated[StrictStr, Field(min_length=1, max_length=4096)] | StrictBool

    @model_validator(mode="after")
    def require_configuration_type(self) -> ConfigurationEquals:
        if type(self.expected) is not CONFIGURATION_TYPES[self.field]:
            raise ValueError("configuration target type mismatch")
        return self


class PermissionIncludes(ConditionContract):
    node_id: NodeId
    kind: Literal["permission_includes"]
    permission: Label


class InputChannelEnabled(ConditionContract):
    node_id: NodeId
    kind: Literal["input_channel_enabled"]
    channel: Literal["public_api", "uploaded_documents", "retrieved_web_content"]
    expected: bool = Field(default=True, strict=True)


class NetworkReachable(ConditionContract):
    node_id: NodeId
    kind: Literal["network_reachable"]
    field: Literal["public_endpoint", "outbound_network_allowed"]
    expected: bool = Field(default=True, strict=True)


class InventoryProvesAbsence(ConditionContract):
    node_id: NodeId
    kind: Literal["inventory_proves_absence"]
    ecosystem: Label
    package_key: Label
    declared_scope: Label


class MitigationConfirmed(ConditionContract):
    node_id: NodeId
    kind: Literal["mitigation_confirmed"]
    mitigation_key: Label
    expected: bool = Field(default=True, strict=True)


class AllOf(ConditionContract):
    node_id: NodeId
    kind: Literal["all_of"]
    children: tuple[ConditionNode, ...] = Field(min_length=1, max_length=63)


class AnyOf(ConditionContract):
    node_id: NodeId
    kind: Literal["any_of"]
    children: tuple[ConditionNode, ...] = Field(min_length=1, max_length=63)


ConditionLeaf = (
    ComponentMatches
    | VersionInRange
    | ConfigurationEquals
    | PermissionIncludes
    | InputChannelEnabled
    | NetworkReachable
    | InventoryProvesAbsence
    | MitigationConfirmed
)
ConditionNode = Annotated[ConditionLeaf | AllOf | AnyOf, Field(discriminator="kind")]
AllOf.model_rebuild()
AnyOf.model_rebuild()
CONDITION_ADAPTER: TypeAdapter[ConditionNode] = TypeAdapter(ConditionNode)


class EvidenceReference(ConditionContract):
    """Caller checked coordinates/support; pure checks cannot authenticate stored source text."""

    evidence_id: Label
    source_id: Label
    document_id: Label
    revision_id: Label
    block_id: Label
    start_offset: int = Field(ge=0, strict=True)
    end_offset: int = Field(ge=1, strict=True)
    quote_text: str = Field(min_length=1, max_length=2000)
    quote_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    scope: VisibilityScope
    support_kind: Literal["supports", "refutes", "context"]
    validation_status: Literal["validated", "unverified"]

    @model_validator(mode="after")
    def require_quote_consistency(self) -> EvidenceReference:
        if self.end_offset - self.start_offset != len(self.quote_text):
            raise ValueError("quote coordinate length mismatch")
        if hashlib.sha256(self.quote_text.encode("utf-8")).hexdigest() != self.quote_sha256:
            raise ValueError("quote digest mismatch")
        return self


class ConditionFact(ConditionContract):
    """Only source-supported mitigation observations can supply a typed leaf value."""

    claim_id: Label
    asset_snapshot_id: Label
    mitigation_key: Label
    value: StrictBool | None
    claim_status: ClaimStatus
    claim_origin: ClaimOrigin
    condition_scope: RuleKind
    scope: VisibilityScope
    source_id: Label
    document_id: Label
    source_revision_id: Label
    evidence: tuple[EvidenceReference, ...] = Field(max_length=64)


class ConditionEvaluation(ConditionContract):
    node_id: NodeId
    value: ConditionValue
    reason_code: str
    evidence_ids: tuple[str, ...] = ()
    asset_field_refs: tuple[str, ...] = ()
    child_results: tuple[ConditionEvaluation, ...] = ()
    observed_conflict_ids: tuple[str, ...] = ()
    missing_requirements: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()


def iter_condition_nodes(condition: ConditionNode) -> tuple[ConditionNode, ...]:
    pending = [condition]
    nodes: list[ConditionNode] = []
    while pending:
        node = pending.pop()
        nodes.append(node)
        if isinstance(node, AllOf | AnyOf):
            pending.extend(reversed(node.children))
    return tuple(nodes)


def _check_raw_tree(raw: Mapping[str, object]) -> None:
    pending: list[tuple[Mapping[str, object], int]] = [(raw, 1)]
    identities: set[int] = set()
    while pending:
        node, depth = pending.pop()
        if id(node) in identities:
            raise ConditionInputError("cycle_or_shared_node")
        identities.add(id(node))
        if depth > MAX_CONDITION_DEPTH or len(identities) > MAX_CONDITION_NODES:
            raise ConditionInputError("condition_budget_exceeded")
        children = node.get("children", ())
        if not isinstance(children, list | tuple):
            raise ConditionInputError("invalid_children")
        for child in children:
            if not isinstance(child, Mapping):
                raise ConditionInputError("invalid_child")
            pending.append((child, depth + 1))


def parse_condition_tree(raw: str | bytes | Mapping[str, object]) -> ConditionNode:
    """Reject duplicate JSON keys/cycles before parsing; root counts as depth one."""
    payload = (
        strict_json_object(raw, MAX_CONDITION_BYTES, maximum_nodes=50000)
        if isinstance(raw, str | bytes)
        else raw
    )
    _check_raw_tree(payload)
    condition = CONDITION_ADAPTER.validate_python(payload)
    nodes = iter_condition_nodes(condition)
    if len({node.node_id for node in nodes}) != len(nodes):
        raise ConditionInputError("duplicate_node_id")
    return condition


def condition_digest(condition: ConditionNode) -> str:
    raw = json.dumps(condition.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def combine_condition_values(
    operator: Literal["all_of", "any_of"], values: tuple[ConditionValue, ...]
) -> ConditionValue:
    """Frozen W06 tables; children are evaluated fully before this aggregation."""
    if not values or operator not in {"all_of", "any_of"}:
        raise ConditionInputError("invalid_combination")
    if any(value not in ConditionValue for value in values):
        raise ConditionInputError("invalid_condition_value")
    decisive = ConditionValue.FALSE if operator == "all_of" else ConditionValue.TRUE
    if decisive in values:
        return decisive
    if ConditionValue.CONFLICT in values:
        return ConditionValue.CONFLICT
    if ConditionValue.UNKNOWN in values:
        return ConditionValue.UNKNOWN
    return ConditionValue.TRUE if operator == "all_of" else ConditionValue.FALSE


def _unique(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


def _result(
    node: ConditionNode,
    value: ConditionValue,
    reason: str,
    *,
    refs: tuple[str, ...] = (),
    evidence: tuple[str, ...] = (),
    conflicts: tuple[str, ...] = (),
    limitations: tuple[str, ...] = (),
) -> ConditionEvaluation:
    return ConditionEvaluation(
        node_id=node.node_id,
        value=value,
        reason_code=reason,
        asset_field_refs=refs,
        evidence_ids=evidence,
        observed_conflict_ids=conflicts,
        missing_requirements=(node.node_id,) if value == ConditionValue.UNKNOWN else (),
        limitations=limitations,
    )


def _field_result(
    node: ConditionNode,
    fields: tuple[DeclaredFieldResponse, ...] | None,
    field_name: str,
    expected: str | bool,
    prefix: str,
) -> ConditionEvaluation:
    matches = tuple(field for field in fields or () if field.name == field_name)
    refs = tuple(f"{prefix}:{field.source_field_locator}" for field in matches)
    if not matches or any(field.value is None for field in matches):
        return _result(node, ConditionValue.UNKNOWN, "missing_asset_field", refs=refs)
    values = tuple(
        type(field.value) is type(expected) and field.value == expected for field in matches
    )
    if len(set(values)) > 1:
        return _result(
            node, ConditionValue.CONFLICT, "conflicting_asset_fields", refs=refs, conflicts=refs
        )
    return _result(
        node,
        ConditionValue.TRUE if values[0] else ConditionValue.FALSE,
        "explicit_asset_field",
        refs=refs,
    )


def _evaluate_leaf(
    node: ConditionLeaf,
    snapshot: AssetSnapshotResponse,
    facts: tuple[ConditionFact, ...],
    rule_kind: RuleKind,
) -> ConditionEvaluation:
    prefix = f"snapshot:{snapshot.snapshot_id}"
    if isinstance(node, ConfigurationEquals):
        return _field_result(node, snapshot.configuration, node.field, node.expected, prefix)
    if isinstance(node, InputChannelEnabled):
        return _field_result(node, snapshot.input_channels, node.channel, node.expected, prefix)
    if isinstance(node, NetworkReachable):
        if rule_kind == "software_applicability":
            return _result(node, ConditionValue.UNKNOWN, "network_cannot_decide_software")
        return _field_result(node, snapshot.network_exposure, node.field, node.expected, prefix)
    if isinstance(node, PermissionIncludes):
        if snapshot.tool_permissions is None:
            return _result(node, ConditionValue.UNKNOWN, "missing_permissions")
        value = (
            ConditionValue.TRUE
            if node.permission in snapshot.tool_permissions
            else ConditionValue.FALSE
        )
        return _result(node, value, "explicit_permissions", refs=(f"{prefix}:/tool_permissions",))
    if isinstance(node, MitigationConfirmed):
        matching = tuple(
            fact
            for fact in facts
            if fact.mitigation_key == node.mitigation_key
            and fact.condition_scope == rule_kind
            and fact.asset_snapshot_id == snapshot.snapshot_id
        )
        supported: list[ConditionFact] = []
        conflicts: list[str] = []
        evidence: list[str] = []
        fact_limitations: list[str] = []
        for fact in matching:
            evidence.extend(span.evidence_id for span in fact.evidence)
            valid = tuple(
                span
                for span in fact.evidence
                if span.validation_status == "validated"
                and span.revision_id == fact.source_revision_id
                and span.source_id == fact.source_id
                and span.document_id == fact.document_id
            )
            if fact.claim_origin == ClaimOrigin.MODEL_HYPOTHESIS or not valid:
                fact_limitations.append(f"unconfirmed_fact:{fact.claim_id}")
                continue
            if fact.claim_status == ClaimStatus.DISPUTED:
                conflicts.append(fact.claim_id)
            elif fact.claim_status == ClaimStatus.SUPPORTED:
                if any(span.support_kind == "refutes" for span in valid):
                    conflicts.append(fact.claim_id)
                if any(span.support_kind == "supports" for span in valid):
                    supported.append(fact)
            else:
                fact_limitations.append(f"inactive_or_pending_fact:{fact.claim_id}")
        values = {fact.value for fact in supported if fact.value is not None}
        if len(values) > 1:
            conflicts.extend(fact.claim_id for fact in supported)
        if conflicts:
            return _result(
                node,
                ConditionValue.CONFLICT,
                "conflicting_source_facts",
                evidence=_unique(tuple(evidence)),
                conflicts=_unique(tuple(conflicts)),
                limitations=tuple(fact_limitations),
            )
        if not values:
            return _result(
                node,
                ConditionValue.UNKNOWN,
                "missing_supported_mitigation",
                evidence=_unique(tuple(evidence)),
                limitations=tuple(fact_limitations),
            )
        value = ConditionValue.TRUE if next(iter(values)) == node.expected else ConditionValue.FALSE
        return _result(
            node,
            value,
            "supported_mitigation",
            evidence=_unique(tuple(evidence)),
            limitations=tuple(fact_limitations),
        )
    if isinstance(node, VersionInRange):
        ecosystem, package_key = node.assertion.ecosystem, node.assertion.package_key
    else:
        ecosystem, package_key = node.ecosystem, node.package_key
    components = tuple(
        component
        for component in snapshot.components
        if component.ecosystem == ecosystem
        and package_key in {component.purl, component.package_name}
    )
    refs = tuple(f"{prefix}:{component.source_field_locator}" for component in components)
    if isinstance(node, ComponentMatches):
        value = ConditionValue.TRUE if components else ConditionValue.UNKNOWN
        return _result(
            node, value, "component_present" if components else "component_not_observed", refs=refs
        )
    if isinstance(node, InventoryProvesAbsence):
        if components:
            return _result(node, ConditionValue.FALSE, "component_present", refs=refs)
        if (
            snapshot.inventory_completeness != "complete_for_declared_scope"
            or node.declared_scope not in snapshot.declared_scope
        ):
            return _result(node, ConditionValue.UNKNOWN, "inventory_scope_incomplete")
        return _result(
            node,
            ConditionValue.TRUE,
            "complete_inventory_proves_absence",
            refs=(f"{prefix}:/inventory_completeness", f"{prefix}:/declared_scope"),
        )
    if not components:
        return _result(node, ConditionValue.UNKNOWN, "component_not_observed")
    results = tuple(
        evaluate_version_assertion(
            node.assertion,
            package_key=node.assertion.package_key,
            ecosystem=component.ecosystem,
            version=component.version,
            version_scheme=component.version_scheme,
            range_complete=node.range_complete,
        )
        for component in components
    )
    limitations = _unique(
        tuple(
            reason
            for result in results
            for reason in (result.reason, *result.unresolved_reasons)
            if result.status in {"unknown", "unsupported"} or reason in result.unresolved_reasons
        )
    )
    statuses = {result.status for result in results}
    if "affected" in statuses and "not_affected" in statuses:
        return _result(
            node,
            ConditionValue.CONFLICT,
            "conflicting_component_versions",
            refs=refs,
            conflicts=refs,
            limitations=limitations,
        )
    if "unknown" in statuses or "unsupported" in statuses:
        return _result(
            node, ConditionValue.UNKNOWN, "version_undecidable", refs=refs, limitations=limitations
        )
    value = ConditionValue.TRUE if statuses == {"affected"} else ConditionValue.FALSE
    return _result(node, value, "version_range_match", refs=refs, limitations=limitations)


def evaluate_condition_tree(
    condition: ConditionNode,
    asset_snapshot: AssetSnapshotResponse,
    *,
    access_scope: AccessScope,
    supporting_facts: tuple[ConditionFact, ...] = (),
    rule_kind: RuleKind = "software_applicability",
) -> ConditionEvaluation:
    """No IO/LLM; supplied scope must come from authentication, not the request body."""
    access_scope.requires(READ_ASSET)
    access_scope.enforce_visible("tenant", asset_snapshot.tenant_id)
    if rule_kind not in {"software_applicability", "observed_path", "research_prerequisites"}:
        raise ConditionInputError("unsupported_rule_kind")
    if len(supporting_facts) > 64:
        raise ConditionInputError("fact_budget_exceeded")
    asset_snapshot = AssetSnapshotResponse.model_validate(asset_snapshot.model_dump(mode="python"))
    supporting_facts = tuple(
        ConditionFact.model_validate(fact.model_dump(mode="python")) for fact in supporting_facts
    )
    condition = parse_condition_tree(condition.model_dump(mode="python"))
    for fact in supporting_facts:
        access_scope.enforce_visible(fact.scope.visibility, fact.scope.tenant_id)
        for span in fact.evidence:
            access_scope.enforce_visible(span.scope.visibility, span.scope.tenant_id)
    for fields, allowed in (
        (asset_snapshot.configuration, CONFIGURATION_TYPES),
        (asset_snapshot.input_channels, INPUT_CHANNELS),
        (asset_snapshot.network_exposure, NETWORK_FIELDS),
    ):
        if any(field.name not in allowed for field in fields or ()):
            raise ConditionInputError("unsupported_asset_field")
        for field in fields or ():
            expected_type = (
                CONFIGURATION_TYPES[field.name] if allowed is CONFIGURATION_TYPES else bool
            )
            if field.value is not None and type(field.value) is not expected_type:
                raise ConditionInputError("invalid_asset_field_type")

    def evaluate(node: ConditionNode) -> ConditionEvaluation:
        if not isinstance(node, AllOf | AnyOf):
            return _evaluate_leaf(node, asset_snapshot, supporting_facts, rule_kind)
        children = tuple(evaluate(child) for child in node.children)
        return ConditionEvaluation(
            node_id=node.node_id,
            value=combine_condition_values(node.kind, tuple(child.value for child in children)),
            reason_code=node.kind,
            child_results=children,
            evidence_ids=_unique(tuple(ref for child in children for ref in child.evidence_ids)),
            asset_field_refs=_unique(
                tuple(ref for child in children for ref in child.asset_field_refs)
            ),
            observed_conflict_ids=_unique(
                tuple(ref for child in children for ref in child.observed_conflict_ids)
            ),
            missing_requirements=_unique(
                tuple(ref for child in children for ref in child.missing_requirements)
            ),
            limitations=_unique(tuple(ref for child in children for ref in child.limitations)),
        )

    return evaluate(condition)
