"""Bulk source registration preserves revision scope and never writes historical blocks."""

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session
from tests.integration.test_r06_bulk_source_evidence_pg import empty_revision, source_block
from tests.integration.test_r06_catalog_documents_pg import NOW
from tests.integration.test_r06_catalog_documents_pg import catalog_engine as catalog_engine

from ai_intel.infrastructure.content_store import ContentStore
from ai_intel.knowledge.models import document_revisions, evidence, text_blocks
from ai_intel.knowledge.revisions import (
    MissingRevisionError,
    QuoteConsistencyError,
    TenantScopeViolation,
    register_source_revision_blocks,
)

pytestmark = pytest.mark.real_pg


@pytest.mark.parametrize(
    "invalid", ["missing", "historical", "tenant", "public_from_tenant", "other_tenant"]
)
def test_scope_or_revision_rejection_has_no_block_or_evidence_effect(
    catalog_engine, tmp_path, invalid
):
    revision_id = empty_revision(catalog_engine, ContentStore(tmp_path))
    with Session(catalog_engine) as session, session.begin():
        if invalid == "historical":
            session.execute(update(document_revisions).values(is_current=False))
        elif invalid in {"public_from_tenant", "other_tenant"}:
            session.execute(
                update(document_revisions).values(visibility="tenant", tenant_id="other")
            )
        expected = {
            "missing": MissingRevisionError,
            "historical": QuoteConsistencyError,
            "tenant": TenantScopeViolation,
            "public_from_tenant": TenantScopeViolation,
            "other_tenant": TenantScopeViolation,
        }[invalid]
        visibility = "public"
        tenant_id = None
        if invalid == "tenant":
            visibility, tenant_id = "tenant", "other"
        elif invalid == "other_tenant":
            visibility, tenant_id = "tenant", "different"
        with pytest.raises(expected):
            register_source_revision_blocks(
                session,
                "does-not-exist" if invalid == "missing" else revision_id,
                (source_block(),),
                visibility,
                tenant_id,
                NOW,
                attach_full_block_evidence=True,
            )
        for table in (text_blocks, evidence):
            assert session.scalar(select(func.count()).select_from(table)) == 0
