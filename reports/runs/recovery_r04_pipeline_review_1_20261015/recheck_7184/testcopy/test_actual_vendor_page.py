"""Real public page replay; empty optional package identity must remain unknown."""
import hashlib
import json
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from test_r04_source_documents import NOW, page_engine, persist

from ai_intel.infrastructure.content_store import ContentStore
from ai_intel.ingestion.source_documents import SourceResponse
from ai_intel.ingestion.sources.vendor_advisories import normalize_vendor_advisory
from ai_intel.knowledge.persistence_models import claims

BODY=Path('/mnt/d/dianzi/reports/runs/recovery_r04_pipeline_review_1_20261015/public_inputs/vllm_actual_page_10.json').read_bytes()
URL='https://api.github.com/repos/vllm-project/vllm/security-advisories?per_page=10&state=published&page=1'
assert hashlib.sha256(BODY).hexdigest()=='f5007db50489ecebbbfec5d8cc8798eb18cff1d12faf503795ce97c85e6894e1'

def test_actual_empty_package_identity_is_unknown_with_raw_range_intact():
    record=json.loads(BODY)[5]
    assert record['ghsa_id']=='GHSA-5fj9-pfhr-6j48'
    normalized=normalize_vendor_advisory(record,repository='vllm-project/vllm')
    assert normalized.vulnerabilities[0].package_name is None
    assert normalized.vulnerabilities[0].package_ecosystem is None
    assert normalized.vulnerabilities[0].affected_range=='< v0.30.0'
    assert normalized.vulnerabilities[0].patched_version=='>= 0.30.0'

@pytest.mark.real_pg
def test_actual_page_persists_all_members_without_invented_package_fact(page_engine,tmp_path):
    store=ContentStore(tmp_path)
    saved=persist(page_engine,store,SourceResponse('vllm_vendor',BODY,URL,NOW))
    assert len(saved.revision_ids)==10
    assert store.read_verified(saved.response_content_hash)==BODY
    with Session(page_engine) as session:
        target=saved.revision_ids[5]
        assert session.scalar(select(func.count()).select_from(claims).where(claims.c.source_revision_id==target,claims.c.predicate=='affected_product'))==0
        assert session.scalar(select(func.count()).select_from(claims).where(claims.c.source_revision_id==target,claims.c.predicate.in_(['vulnerable_version','patched_version','version_range'])))==0
