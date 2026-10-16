"""Daily/weekly proposals preserve the selected cutoff and first observation window."""

from datetime import datetime, timedelta
from typing import Literal

from pydantic import TypeAdapter

from ai_intel.domain.enums import ClaimStatus, FreshnessStatus
from ai_intel.domain.values import UtcTimestamp
from ai_intel.recommendations.contracts import (
    MAX_CANDIDATES,
    RecommendationBatch,
    ReportCandidate,
    ReportStopReason,
)
from ai_intel.recommendations.policy import candidate_order, require_item_budget


def build_report_candidate(
    batch: RecommendationBatch,
    *,
    frequency: Literal["day", "week"],
    cutoff_at: datetime,
    generated_at: datetime,
    max_items: int = MAX_CANDIDATES,
) -> ReportCandidate:
    """Window is (cutoff - 1/7 days, cutoff]; older source dates never hide late observations.

    Historical reports retain validity_as_of and separate current_status metadata.
    The caller must freeze/select historical PG facts; no present state is backdated here.
    """
    require_item_budget(max_items)
    cutoff = TypeAdapter(UtcTimestamp).validate_python(cutoff_at)
    generated = TypeAdapter(UtcTimestamp).validate_python(generated_at)
    batch = RecommendationBatch.model_validate(batch.model_dump(mode="python"))
    if frequency not in {"day", "week"}:
        raise ValueError("unsupported_report_frequency")
    if cutoff != batch.cutoff_at or generated < cutoff:
        raise ValueError("report_cutoff_mismatch")
    window_start = cutoff - timedelta(days=1 if frequency == "day" else 7)
    items = []
    for candidate in batch.candidates:
        if (
            candidate.tenant_id != batch.subscription.tenant_id
            or candidate.user_id != batch.subscription.user_id
            or candidate.key.subscription_id != batch.subscription.subscription_id
            or candidate.validity_as_of != cutoff
            or candidate.observed_at > cutoff
            or candidate.valid_from > cutoff
            or (candidate.valid_until is not None and candidate.valid_until <= cutoff)
            or candidate.freshness_at_cutoff != FreshnessStatus.CURRENT
            or candidate.current_state_checked_at > generated
            or (
                candidate.current_state_checked_at == cutoff
                and candidate.current_status in {ClaimStatus.WITHDRAWN, ClaimStatus.SUPERSEDED}
            )
        ):
            raise ValueError("report_candidate_scope_mismatch")
        if window_start < candidate.observed_at <= cutoff:
            items.append(candidate)
    items.sort(key=candidate_order)
    selected = items[:max_items] if batch.subscription.enabled else []
    continuation = tuple(item.key for item in items[max_items:]) + batch.continuation_keys
    partial = bool(continuation) or batch.partial
    stop_reason: ReportStopReason = (
        "disabled"
        if not batch.subscription.enabled
        else ("item_budget" if partial else ("complete" if selected else "no_items_in_window"))
    )
    return ReportCandidate(
        subscription_id=batch.subscription.subscription_id,
        tenant_id=batch.subscription.tenant_id,
        user_id=batch.subscription.user_id,
        frequency=frequency,
        window_start=window_start,
        cutoff_at=cutoff,
        generated_at=generated,
        supported_risks=tuple(item for item in selected if item.kind == "supported_risk"),
        verification_items=tuple(
            item for item in selected if item.kind == "prioritize_verification"
        ),
        excluded_items=tuple(item for item in selected if item.kind == "excluded_with_evidence"),
        intelligence_updates=tuple(item for item in selected if item.kind == "intelligence_update"),
        partial=partial,
        continuation_keys=continuation,
        stop_reason=stop_reason,
        limitations=(
            "candidate_only_requires_pg_authorization_and_final_validity_check",
            "window_uses_first_material_observation_not_source_publication",
            "historical_validity_is_not_current_validity",
        ),
    )
