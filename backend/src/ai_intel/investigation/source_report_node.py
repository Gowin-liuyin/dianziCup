"""Read original source reports for one deterministic enrichment node."""

import math
import time

from ai_intel.investigation.graph_contracts import InvestigationRequest
from ai_intel.knowledge.structured_fact_proofs import (
    StructuredFactProofRead,
    StructuredFactProofReader,
    StructuredFactProofRequest,
)


def read_enrichment_source_reports(
    reader: StructuredFactProofReader,
    request: InvestigationRequest,
    deadline_monotonic: float,
) -> tuple[StructuredFactProofRead, ...]:
    """Revalidate all references before IO and share the caller's original five-second
    deadline. Empty references return no reports; the caller must record the evidence gap
    and enforce receipt bytes. Every original report and reader exception is preserved.
    """
    if not isinstance(reader, StructuredFactProofReader) or not isinstance(
        request, InvestigationRequest
    ):
        raise TypeError("typed_source_report_reader_and_investigation_request_required")
    if (
        isinstance(deadline_monotonic, bool)
        or not isinstance(deadline_monotonic, int | float)
        or not math.isfinite(deadline_monotonic)
    ):
        raise ValueError("finite_source_report_deadline_required")
    remaining_seconds = deadline_monotonic - time.monotonic()
    if remaining_seconds > 5:
        raise ValueError("source_report_deadline_exceeds_five_seconds")
    if remaining_seconds <= 0:
        raise TimeoutError("source_report_deadline_exhausted")
    current_request = InvestigationRequest.model_validate(request.model_dump())
    proof_requests = tuple(
        StructuredFactProofRequest(**reference.model_dump())
        for reference in current_request.evidence_refs
    )
    reports = []
    for proof_request in proof_requests:
        if time.monotonic() >= deadline_monotonic:
            raise TimeoutError("source_report_deadline_exhausted")
        reports.append(reader.read(proof_request, deadline_monotonic))
    return tuple(reports)
