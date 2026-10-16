"""Bind the reviewed source-report reader to the default deterministic enrichment node."""

from sqlalchemy.engine import Connection

from ai_intel.api.actor_references import ActorReference
from ai_intel.api.knowledge_contracts import DataMode
from ai_intel.domain.access import AccessScope
from ai_intel.infrastructure.content_store import ContentStorage
from ai_intel.knowledge.structured_fact_proofs import StructuredFactProofReader


def build_source_report_reader(
    connection: Connection,
    actor_reference: ActorReference,
    access_scope: AccessScope,
    content_store: ContentStorage,
    data_mode: DataMode,
) -> StructuredFactProofReader:
    """The caller supplies server authority and an idle connection, then uses the original
    strict three-UUID request and at most five-second deadline. No connection, tool budget,
    fact, cache or proof model is created here; the shared reader retains every fence.
    """
    return StructuredFactProofReader(
        connection, actor_reference, access_scope, content_store, data_mode
    )
