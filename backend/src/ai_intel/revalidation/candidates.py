"""Read-only PG discovery over current authorized assets and append-only assessments."""

from __future__ import annotations

import base64
import hmac
import re
from dataclasses import dataclass
from datetime import UTC, datetime

from pydantic import SecretStr, ValidationError
from sqlalchemy import select, text
from sqlalchemy.engine import Engine, RowMapping
from sqlalchemy.orm import Session

from ai_intel.api.auth_state import lock_authenticated_scope
from ai_intel.assessment.conditions import (
    ComponentMatches,
    InventoryProvesAbsence,
    VersionInRange,
    iter_condition_nodes,
)
from ai_intel.assessment.persistence_contracts import AssessmentReceipt, AssessmentScopeWatch
from ai_intel.assessment.rule_persistence import condition_rule_versions, stored_rule
from ai_intel.assessment.rules import ConditionRule
from ai_intel.assets.inventory_contracts import AssetSnapshotResponse
from ai_intel.domain.access import READ_ASSET, AccessScope, CrossTenantAccessError
from ai_intel.knowledge.models import scope_epochs
from ai_intel.knowledge.persistence import publication_payload_digest
from ai_intel.knowledge.persistence_models import change_events
from ai_intel.revalidation.candidate_contracts import (
    AssessmentChangeCandidate,
    CandidateContinuation,
    CandidatePage,
    CandidateReason,
)

MAX_SCANNED_ROWS = 500
MAX_CHANGE_REFERENCES = 256
QUERY_VERSION = "r16-pg-candidates-1:asset_id,kind,reference_id"


class CandidateDiscoveryError(ValueError):
    """Fixed codes distinguish invalid epochs/cursors from missing configuration."""


@dataclass(frozen=True)
class AffectedAssessmentScope:
    changed_ids: frozenset[str]
    package_keys: frozenset[str] = frozenset()
    event_ids: frozenset[str] = frozenset()
    rule_ids: frozenset[str] = frozenset()
    asset_ids: frozenset[str] = frozenset()
    fallback_reason: str | None = None


def rule_package_keys(rule: ConditionRule) -> frozenset[str]:
    """Use exactly the evaluator's ecosystem/package identity, including purls."""
    keys: set[str] = set()
    for node in iter_condition_nodes(rule.condition_ast):
        if isinstance(node, VersionInRange):
            keys.add(node.assertion.ecosystem + ":" + node.assertion.package_key)
        elif isinstance(node, ComponentMatches | InventoryProvesAbsence):
            keys.add(node.ecosystem + ":" + node.package_key)
    return frozenset(keys)


def candidate_reasons(
    affected: AffectedAssessmentScope,
    snapshot: AssetSnapshotResponse,
    assessment: AssessmentReceipt | None = None,
    watch: AssessmentScopeWatch | None = None,
) -> tuple[CandidateReason, ...]:
    """Union historical references, explicit empty watches and current package candidates."""
    reasons: set[CandidateReason] = set()
    if affected.fallback_reason:
        reasons.add("partition_fallback")
    if snapshot.asset_id in affected.asset_ids:
        reasons.add("old_dependency" if assessment else "new_package_association")
    if assessment is not None:
        inputs = assessment.prepared.inputs
        references = {
            assessment.asset_id,
            assessment.asset_snapshot_id,
            assessment.event_id,
            assessment.rule_id,
            *inputs.rule.supporting_claim_ids,
            *inputs.rule.source_span_ids,
            *inputs.active_revision_ids,
        }
        for source in inputs.sources:
            references.update((source.source_id, source.document_id, source.revision_id))
        if references & affected.changed_ids:
            reasons.add("old_dependency")
        if watch is None:
            reasons.add("missing_scope_watch")
        elif (
            set(watch.event_ids) & affected.event_ids
            or set(watch.package_keys) & affected.package_keys
            or {watch.rule_id, *watch.selected_rule_ids} & affected.rule_ids
        ):
            reasons.add("scope_watch")
        if watch is not None and any(value is None for value in watch.scope_epoch_map.values()):
            reasons.add("partition_fallback")
        if reasons and watch is not None and watch.no_published_rule:
            reasons.add("empty_rule_scope")
    else:
        packages = {
            component.ecosystem + ":" + identity
            for component in snapshot.components
            for identity in (component.package_name, component.purl)
            if identity is not None
        }
        if packages & affected.package_keys:
            reasons.add("new_package_association")
        elif (
            affected.package_keys
            and snapshot.inventory_completeness != "complete_for_declared_scope"
        ):
            reasons.add("partition_fallback")
    return tuple(sorted(reasons))


def _signing_bytes(key: SecretStr | None) -> bytes:
    if key is None:
        raise CandidateDiscoveryError("candidate_cursor_signing_key_not_configured")
    value = key.get_secret_value()
    if re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise CandidateDiscoveryError("candidate_cursor_signing_key_invalid")
    return bytes.fromhex(value)


def _encode_cursor(cursor: CandidateContinuation, key: bytes) -> str:
    payload = cursor.model_dump_json().encode()
    signature = hmac.digest(key, payload, "sha256")
    return base64.urlsafe_b64encode(signature + payload).decode()


def _decode_cursor(value: str, key: bytes) -> CandidateContinuation:
    if not isinstance(value, str) or len(value) > 4096:
        raise CandidateDiscoveryError("candidate_cursor_invalid")
    try:
        decoded = base64.b64decode(value, altchars=b"-_", validate=True)
        signature, payload = decoded[:32], decoded[32:]
        if not hmac.compare_digest(signature, hmac.digest(key, payload, "sha256")):
            raise ValueError
        return CandidateContinuation.model_validate_json(payload)
    except (ValueError, ValidationError):
        raise CandidateDiscoveryError("candidate_cursor_invalid") from None


def _references(payload: object) -> dict[str, set[str]]:
    """Recognize fixed persisted reference fields; unknown shapes force scope fallback."""
    kinds = {
        "source",
        "document",
        "revision",
        "evidence",
        "claim",
        "event",
        "rule",
        "asset",
        "entity",
        "alias",
    }
    references: dict[str, set[str]] = {kind: set() for kind in kinds}
    pending = [payload]
    visited = 0
    while pending:
        value = pending.pop()
        visited += 1
        if visited > 10000:
            raise CandidateDiscoveryError("candidate_change_payload_budget_exceeded")
        if isinstance(value, dict):
            for name, child in value.items():
                kind = str(name).removesuffix("_id").removesuffix("_ids")
                if name == "source_revision_id" or name == "previous_revision_id":
                    kind = "revision"
                if name == "source_span_ids":
                    kind = "evidence"
                if name == "supporting_claim_ids":
                    kind = "claim"
                if kind in kinds:
                    values = child if isinstance(child, list | tuple) else (child,)
                    for reference in values:
                        if isinstance(reference, str):
                            references[kind].add(reference)
                        elif isinstance(reference, dict) and isinstance(
                            reference.get("value"), str
                        ):
                            references[kind].add(reference["value"])
                pending.append(child)
        elif isinstance(value, list | tuple):
            pending.extend(value)
    if sum(map(len, references.values())) > MAX_CHANGE_REFERENCES:
        raise CandidateDiscoveryError("candidate_change_reference_budget_exceeded")
    return references


def _visible(alias: str, *, tenant_input: str = "CAST(:tenant AS TEXT)") -> str:
    """A public parent's null tenant is false, with an explicit psycopg parameter type."""
    return (
        f"(({alias}.visibility='public' AND {alias}.tenant_id IS NULL) OR "
        f"({tenant_input} IS NOT NULL AND {alias}.visibility='tenant' "
        f"AND {alias}.tenant_id={tenant_input}))"
    )


SOURCE_JOIN = (
    "document_revisions r JOIN documents d ON d.document_id=r.document_id "
    "JOIN sources s ON s.source_id=d.source_id"
)
SOURCE_VISIBLE = " AND ".join(_visible(alias) for alias in ("r", "d", "s"))


def _event_guard(alias: str) -> str:
    visibility = " AND ".join(
        _visible(name, tenant_input=f"{alias}.tenant_id") for name in ("r", "d", "s")
    )
    return (
        f"{_visible(alias)} AND NOT EXISTS (SELECT 1 FROM event_documents ed "
        f"JOIN {SOURCE_JOIN} ON r.revision_id=ed.revision_id "
        f"WHERE ed.event_id={alias}.event_id AND NOT ({visibility}))"
    )


def _rule_guard(rule_alias: str, event_alias: str) -> str:
    source_visible = " AND ".join(
        _visible(name, tenant_input=f"{rule_alias}.tenant_id") for name in ("r", "d", "s", "f")
    )
    return (
        f"{_visible(rule_alias)} AND {_event_guard(event_alias)} "
        f"AND ({event_alias}.visibility='public' OR ({rule_alias}.tenant_id IS NOT NULL AND "
        f"{event_alias}.tenant_id={rule_alias}.tenant_id)) "
        f"AND NOT EXISTS (SELECT 1 FROM evidence f JOIN {SOURCE_JOIN} "
        "ON r.revision_id=f.revision_id WHERE f.evidence_id IN "
        f"(SELECT jsonb_array_elements_text({rule_alias}.rule_payload->'source_span_ids')) "
        f"AND NOT ({source_visible}))"
    )


ASSESSMENT_SOURCE_GUARD = (
    "NOT EXISTS (SELECT 1 FROM "
    "jsonb_array_elements(a.result_payload->'prepared'->'inputs'->'sources') p "
    "LEFT JOIN document_revisions r ON r.revision_id=p->>'revision_id' "
    "LEFT JOIN documents d ON d.document_id=r.document_id AND d.document_id=p->>'document_id' "
    "LEFT JOIN sources s ON s.source_id=d.source_id AND s.source_id=p->>'source_id' "
    "WHERE s.source_id IS NULL OR NOT ("
    + " AND ".join(_visible(alias, tenant_input="v.tenant_id") for alias in ("r", "d", "s"))
    + "))"
)

SOURCE_STAMP = (
    "(SELECT coalesce(string_agg(concat(r.revision_id,r.visibility,r.tenant_id,"
    "d.visibility,d.tenant_id,s.visibility,s.tenant_id),'|' ORDER BY r.revision_id),'') "
    f"FROM {SOURCE_JOIN} WHERE r.revision_id IN "
    "(SELECT ed.revision_id FROM event_documents ed WHERE ed.event_id=e.event_id) "
    "OR r.revision_id IN (SELECT p->>'revision_id' FROM "
    "jsonb_array_elements(a.result_payload->'prepared'->'inputs'->'sources') p))"
)

SUPPORT_STAMP = (
    "(SELECT coalesce(string_agg(concat(c.claim_id,c.visibility,c.tenant_id,"
    "f.evidence_id,f.visibility,f.tenant_id),'|' ORDER BY c.claim_id,f.evidence_id),'') "
    "FROM jsonb_array_elements(a.result_payload->'prepared'->'inputs'->'supports') p "
    "JOIN claims c ON c.claim_id=p->'binding'->>'claim_id' "
    "JOIN evidence f ON f.evidence_id=p->'binding'->>'evidence_id')"
)

PARTITION_QUERY = (
    "SELECT x.asset_id,'asset' AS kind,x.asset_id AS reference_id,x.current_snapshot_id,"
    "n.canonical_payload AS snapshot_payload,'{}'::jsonb AS result_payload,"
    "NULL::jsonb AS watch_payload,'' AS source_stamp,'' AS stored_rule_id,"
    "0 AS stored_rule_version,'' AS stored_event_id,'' AS stored_previous_snapshot_id "
    "FROM assets x "
    "JOIN asset_snapshots n ON n.asset_id=x.asset_id AND n.tenant_id=x.tenant_id "
    "AND n.snapshot_id=x.current_snapshot_id WHERE x.tenant_id=:tenant AND x.active "
    "UNION ALL SELECT x.asset_id,'assessment',a.assessment_id,x.current_snapshot_id,"
    "n.canonical_payload,a.result_payload,to_jsonb(w),"
    f"concat({SOURCE_STAMP},{SUPPORT_STAMP},v.status,v.visibility,v.tenant_id,"
    "e.visibility,e.tenant_id,e.status),a.rule_id,a.rule_version,a.event_id,"
    "a.asset_snapshot_id FROM assessment_results a "
    "JOIN assets x ON x.asset_id=a.asset_id AND x.tenant_id=a.tenant_id "
    "JOIN asset_snapshots n ON n.asset_id=x.asset_id AND n.tenant_id=x.tenant_id "
    "AND n.snapshot_id=x.current_snapshot_id "
    "JOIN condition_rule_versions v ON v.rule_id=a.rule_id AND v.version=a.rule_version "
    "JOIN events e ON e.event_id=a.event_id "
    "LEFT JOIN assessment_scope_watches w ON w.assessment_id=a.assessment_id "
    "AND w.tenant_id=a.tenant_id "
    f"WHERE a.tenant_id=:tenant AND {_rule_guard('v', 'e')} "
    f"AND {ASSESSMENT_SOURCE_GUARD} "
    "AND NOT EXISTS (SELECT 1 FROM claims c WHERE c.claim_id IN (SELECT p->'binding'->>'claim_id' "
    "FROM jsonb_array_elements(a.result_payload->'prepared'->'inputs'->'supports') p) "
    f"AND NOT ({_visible('c', tenant_input='v.tenant_id')})) "
    "AND NOT EXISTS (SELECT 1 FROM evidence f WHERE f.evidence_id IN "
    "(SELECT p->'binding'->>'evidence_id' "
    "FROM jsonb_array_elements(a.result_payload->'prepared'->'inputs'->'supports') p) "
    f"AND NOT ({_visible('f', tenant_input='v.tenant_id')}))"
)


class CandidateDiscoveryService:
    """Authenticated bounded discovery; mutations and worker dispatch belong to later slices."""

    def __init__(
        self, engine: Engine, session_token: str, cursor_signing_key: SecretStr | None = None
    ) -> None:
        self.engine = engine
        self._session_token = session_token
        self._cursor_key = _signing_bytes(cursor_signing_key)

    def _authorize_change(self, session: Session, scope: AccessScope, row: RowMapping) -> None:
        tenant = None if row["scope_key"] == "public" else scope.tenant_id
        parameters = {"tenant": tenant}
        references = _references(row["payload"])
        queries = {
            "source": "SELECT source_id FROM sources s WHERE source_id=:reference "
            f"AND {_visible('s')}",
            "document": "SELECT document_id FROM documents d JOIN sources s USING(source_id) "
            f"WHERE document_id=:reference AND {_visible('d')} AND {_visible('s')}",
            "revision": f"SELECT revision_id FROM {SOURCE_JOIN} WHERE revision_id=:reference "
            f"AND {SOURCE_VISIBLE}",
            "evidence": f"SELECT f.evidence_id FROM evidence f JOIN {SOURCE_JOIN} "
            f"ON r.revision_id=f.revision_id WHERE f.evidence_id=:reference "
            f"AND {_visible('f')} AND {SOURCE_VISIBLE}",
            "claim": "SELECT c.claim_id FROM claims c WHERE c.claim_id=:reference "
            f"AND {_visible('c')} "
            "AND NOT EXISTS (SELECT 1 FROM claim_assertions ca JOIN "
            f"{SOURCE_JOIN} ON r.revision_id=ca.revision_id WHERE ca.claim_id=c.claim_id "
            f"AND NOT ({SOURCE_VISIBLE}))",
            "event": "SELECT event_id FROM events e WHERE event_id=:reference "
            f"AND {_event_guard('e')}",
            "rule": f"SELECT rule_id FROM condition_rule_versions v JOIN events e USING(event_id) "
            f"WHERE rule_id=:reference AND {_rule_guard('v', 'e')} "
            "AND NOT EXISTS (SELECT 1 FROM condition_rule_versions v2 "
            "JOIN events e2 USING(event_id) "
            f"WHERE v2.rule_id=v.rule_id AND NOT ({_rule_guard('v2', 'e2')}))",
            "asset": "SELECT asset_id FROM assets WHERE asset_id=:reference AND tenant_id=:tenant",
            "alias": f"SELECT z.alias_id FROM entity_aliases z JOIN entities h USING(entity_id) "
            f"JOIN {SOURCE_JOIN} ON r.revision_id=z.revision_id AND s.source_id=z.source_id "
            f"WHERE z.alias_id=:reference AND {_visible('h')} AND {SOURCE_VISIBLE}",
            "entity": f"SELECT entity_id FROM entities h WHERE entity_id=:reference "
            f"AND {_visible('h')} AND NOT EXISTS (SELECT 1 FROM entity_aliases z "
            f"JOIN {SOURCE_JOIN} ON r.revision_id=z.revision_id AND s.source_id=z.source_id "
            "WHERE z.entity_id=h.entity_id AND NOT ("
            + " AND ".join(_visible(alias, tenant_input="h.tenant_id") for alias in ("r", "d", "s"))
            + "))",
        }
        for kind, ids in references.items():
            for reference in sorted(ids):
                if (
                    session.execute(
                        text(queries[kind]), {**parameters, "reference": reference}
                    ).first()
                    is None
                ):
                    raise CrossTenantAccessError("resource not found")
        changed = row["entity_ids"]
        if not isinstance(changed, list) or len(changed) > MAX_CHANGE_REFERENCES:
            raise CandidateDiscoveryError("candidate_change_reference_budget_exceeded")
        for reference in changed:
            if not isinstance(reference, str):
                raise CandidateDiscoveryError("candidate_change_reference_invalid")
            for kind, table, column in (
                ("source", "sources", "source_id"),
                ("document", "documents", "document_id"),
                ("revision", "document_revisions", "revision_id"),
                ("evidence", "evidence", "evidence_id"),
                ("claim", "claims", "claim_id"),
                ("event", "events", "event_id"),
                ("rule", "condition_rule_versions", "rule_id"),
                ("asset", "assets", "asset_id"),
                ("entity", "entities", "entity_id"),
                ("alias", "entity_aliases", "alias_id"),
            ):
                exists = (
                    session.execute(
                        text(f"SELECT 1 FROM {table} WHERE {column}=:reference LIMIT 1"),
                        {"reference": reference},
                    ).first()
                    is not None
                )
                if (
                    exists
                    and session.execute(
                        text(queries[kind]), {**parameters, "reference": reference}
                    ).first()
                    is None
                ):
                    raise CrossTenantAccessError("resource not found")

    @staticmethod
    def _affected_scope(
        session: Session, row: RowMapping, target_epoch: int
    ) -> AffectedAssessmentScope:
        changed = frozenset(row["entity_ids"])
        if row["epoch"] != target_epoch:
            return AffectedAssessmentScope(changed, fallback_reason="coalesced_scope_epoch")
        if row["change_type"] in {"condition_rule_published", "condition_rule_retired"}:
            rule_id = row["payload"].get("rule_id")
            versions = tuple(
                session.execute(
                    select(condition_rule_versions)
                    .where(condition_rule_versions.c.rule_id == rule_id)
                    .order_by(condition_rule_versions.c.version)
                    .limit(65)
                ).mappings()
            )
            if not versions or len(versions) > 64:
                return AffectedAssessmentScope(changed, fallback_reason="rule_scope_unbounded")
            rules = tuple(stored_rule(version) for version in versions)
            packages = frozenset(key for rule in rules for key in rule_package_keys(rule))
            broad = any(
                not isinstance(node, ComponentMatches | VersionInRange)
                for rule in rules
                for node in iter_condition_nodes(rule.condition_ast)
                if node.kind not in {"all_of", "any_of"}
            )
            return AffectedAssessmentScope(
                changed,
                packages,
                frozenset(rule.event_id for rule in rules),
                frozenset((rule_id,)),
                fallback_reason="non_package_rule_scope" if broad or not packages else None,
            )
        if row["change_type"] == "asset_snapshot_changed" and row["payload"].get("asset_id"):
            return AffectedAssessmentScope(
                changed, asset_ids=frozenset((row["payload"]["asset_id"],))
            )
        return AffectedAssessmentScope(
            changed, fallback_reason="unknown_or_incomplete_change_scope"
        )

    def discover(
        self, change_id: str, target_epoch: int, *, limit: int = 20, continuation: str | None = None
    ) -> CandidatePage:
        """Return current snapshot refs plus readable history; complete means discovery only."""
        if (
            type(target_epoch) is not int
            or target_epoch < 0
            or type(limit) is not int
            or not 1 <= limit <= 100
        ):
            raise CandidateDiscoveryError("candidate_request_invalid")
        if not isinstance(change_id, str) or not 1 <= len(change_id) <= 200:
            raise CandidateDiscoveryError("candidate_request_invalid")
        with (
            self.engine.connect().execution_options(
                isolation_level="REPEATABLE READ"
            ) as connection,
            Session(bind=connection) as session,
            session.begin(),
        ):
            scope = lock_authenticated_scope(
                session.connection(), self._session_token, datetime.now(UTC)
            )
            scope.requires(READ_ASSET)
            if scope.tenant_id is None:
                raise CrossTenantAccessError("resource not found")
            row = (
                session.execute(
                    select(change_events).where(
                        change_events.c.change_id == change_id,
                        change_events.c.scope_key.in_(("public", "tenant:" + scope.tenant_id)),
                    )
                )
                .mappings()
                .first()
            )
            if row is None:
                raise CrossTenantAccessError("resource not found")
            self._authorize_change(session, scope, row)
            epochs = {"public": None, "tenant:" + scope.tenant_id: None}
            for epoch in session.execute(
                select(scope_epochs).where(scope_epochs.c.scope_key.in_(epochs))
            ).mappings():
                epochs[epoch["scope_key"]] = epoch["epoch"]
            current = epochs[row["scope_key"]]
            if current is None or not row["epoch"] <= target_epoch <= current:
                raise CandidateDiscoveryError("candidate_target_epoch_invalid")
            affected = self._affected_scope(session, row, current)
            query_digest = publication_payload_digest(
                {
                    "version": QUERY_VERSION,
                    "change": row["payload"],
                    "changed_ids": row["entity_ids"],
                    "fallback": affected.fallback_reason,
                    "packages": sorted(affected.package_keys),
                }
            )
            partition = session.execute(
                text(
                    "SELECT md5(coalesce(string_agg(md5(row_to_json(p)::text),'' "
                    "ORDER BY asset_id,kind,reference_id),'')) FROM (" + PARTITION_QUERY + ") p"
                ),
                {"tenant": scope.tenant_id},
            ).scalar_one()
            binding = dict(
                change_id=change_id,
                scope_key=row["scope_key"],
                actor_user_id=scope.user_id,
                tenant_id=scope.tenant_id,
                actor_role=scope.role.value,
                permission_version=scope.permission_version,
                requested_epoch=target_epoch,
                scope_epoch_map=epochs,
                query_fingerprint=query_digest,
                partition_fingerprint=partition,
                limit=limit,
            )
            parameters: dict[str, object] = {
                "tenant": scope.tenant_id,
                "scan_limit": MAX_SCANNED_ROWS + 1,
            }
            position_clause = ""
            if continuation is not None:
                cursor = _decode_cursor(continuation, self._cursor_key)
                if any(getattr(cursor, field) != value for field, value in binding.items()):
                    raise CandidateDiscoveryError("candidate_cursor_context_changed")
                parameters.update(
                    after_asset_id=cursor.after_asset_id,
                    after_kind=cursor.after_kind,
                    after_reference_id=cursor.after_reference_id,
                )
                position_clause = (
                    "WHERE (asset_id,kind,reference_id)>"
                    "(:after_asset_id,:after_kind,:after_reference_id) "
                )
            rows = tuple(
                session.execute(
                    text(
                        "SELECT * FROM ("
                        + PARTITION_QUERY
                        + ") p "
                        + position_clause
                        + "ORDER BY asset_id,kind,reference_id LIMIT :scan_limit"
                    ),
                    parameters,
                ).mappings()
            )
            candidates: list[AssessmentChangeCandidate] = []
            scanned = 0
            for item in rows[:MAX_SCANNED_ROWS]:
                snapshot = AssetSnapshotResponse.model_validate(item["snapshot_payload"])
                if (
                    snapshot.asset_id != item["asset_id"]
                    or snapshot.tenant_id != scope.tenant_id
                    or snapshot.snapshot_id != item["current_snapshot_id"]
                ):
                    raise CandidateDiscoveryError("candidate_snapshot_identity_invalid")
                assessment = (
                    AssessmentReceipt.model_validate(item["result_payload"])
                    if item["kind"] == "assessment"
                    else None
                )
                if assessment is not None and (
                    assessment.assessment_id != item["reference_id"]
                    or assessment.tenant_id != scope.tenant_id
                    or assessment.asset_id != item["asset_id"]
                    or assessment.rule_id != item["stored_rule_id"]
                    or assessment.rule_version != item["stored_rule_version"]
                    or assessment.event_id != item["stored_event_id"]
                    or assessment.asset_snapshot_id != item["stored_previous_snapshot_id"]
                ):
                    raise CandidateDiscoveryError("candidate_assessment_identity_invalid")
                watch = None
                if item["watch_payload"] is not None:
                    payload = dict(item["watch_payload"])
                    if payload.pop("assessment_id") != item["reference_id"]:
                        raise CandidateDiscoveryError("candidate_watch_identity_invalid")
                    watch = AssessmentScopeWatch.model_validate(payload)
                    if watch.tenant_id != scope.tenant_id:
                        raise CandidateDiscoveryError("candidate_watch_identity_invalid")
                reasons = candidate_reasons(affected, snapshot, assessment, watch)
                scanned += 1
                if reasons:
                    candidates.append(
                        AssessmentChangeCandidate(
                            asset_id=snapshot.asset_id,
                            asset_snapshot_id=snapshot.snapshot_id,
                            assessment_id=None if assessment is None else assessment.assessment_id,
                            previous_asset_snapshot_id=None
                            if assessment is None
                            else assessment.asset_snapshot_id,
                            watch_assessment_id=None
                            if watch is None or assessment is None
                            else assessment.assessment_id,
                            reasons=reasons,
                        )
                    )
                if len(candidates) == limit:
                    break
            next_cursor = None
            if scanned < len(rows):
                last = rows[scanned - 1]
                next_cursor = _encode_cursor(
                    CandidateContinuation(
                        **binding,
                        after_asset_id=last["asset_id"],
                        after_kind=last["kind"],
                        after_reference_id=last["reference_id"],
                    ),
                    self._cursor_key,
                )
            return CandidatePage(
                change_id=change_id,
                scope_key=row["scope_key"],
                requested_epoch=target_epoch,
                target_epoch=current,
                scope_epoch_map=epochs,
                candidates=tuple(candidates),
                status="partial" if next_cursor else "complete",
                continuation=next_cursor,
                scanned_count=scanned,
                fallback_reason=affected.fallback_reason,
            )
