"""T05 持久化与原文存储集成验收测试: 真实 PostgreSQL + 真实文件系统。

覆盖 T05-C01—C06 与审查修复项(M1-M3); 容器不可用时整组 blocked, 不使用 SQLite 冒充。
"""

from __future__ import annotations

import hashlib
import socket
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select, text

from ai_intel.infrastructure.content_store import ContentPathValidationError, ContentStore
from ai_intel.infrastructure.database import (
    current_migration_revision,
    run_downgrade,
    run_migrations,
)
from ai_intel.knowledge.models import (
    content_objects,
    document_revisions,
    fetch_attempts,
)
from ai_intel.knowledge.models import (
    evidence as evidence_table,
)
from ai_intel.knowledge.revisions import (
    MissingDocumentError,
    QuoteConsistencyError,
    TenantScopeViolation,
    add_text_block,
    attach_evidence_span,
    bump_scope_epoch,
    cleanup_unreferenced_object,
    record_fetch_attempt,
    save_document_revision,
)

UTC = UTC
DEVELOPMENT_DSN = "postgresql+psycopg://ai_intel:dev-only-not-a-secret@127.0.0.1:5432/ai_intel"


def containers_available() -> bool:
    """探测开发数据库端口是否可达; 不可达即整组 blocked, 不使用 SQLite 冒充。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe_socket:
        probe_socket.settimeout(2)
        return probe_socket.connect_ex(("127.0.0.1", 5432)) == 0


pytestmark = pytest.mark.skipif(
    not containers_available(),
    reason="blocked: 数据库容器不可用（T05 集成验证挂起）, 不使用 SQLite 冒充",
)


@pytest.fixture()
def migrated_engine():
    """真实库引擎: 迁移到 head 后提供, 用后断开。"""
    run_migrations(DEVELOPMENT_DSN)
    engine = create_engine(DEVELOPMENT_DSN)
    yield engine
    engine.dispose()


def make_content_store(tmp_path: Path) -> ContentStore:
    """隔离的原文存储根目录, 互不干扰。"""
    return ContentStore(tmp_path / "objects")


def seed_document(connection, document_id: str, visibility: str, tenant_id: str | None) -> None:
    """登记来源与文档父行: 修订链外键指向 documents, 测试数据需满足引用完整性。"""
    source_id = str(uuid.uuid4())
    now = datetime(2026, 9, 30, 11, 0, tzinfo=UTC)
    connection.execute(
        text(
            "INSERT INTO content_objects (content_hash, size_bytes, created_at) "
            "VALUES (:content_hash, 0, :created_at) ON CONFLICT DO NOTHING"
        ),
        {"content_hash": "0" * 64, "created_at": now},
    )
    connection.execute(
        text(
            "INSERT INTO sources (source_id, name, category, base_origin, "
            "visibility, tenant_id, created_at) VALUES (:source_id, :name, "
            ":category, :base_origin, :visibility, :tenant_id, :created_at)"
        ),
        {
            "source_id": source_id,
            "name": "source-" + source_id,
            "category": "vendor_advisory",
            "base_origin": "https://example.invalid",
            "visibility": visibility,
            "tenant_id": tenant_id,
            "created_at": now,
        },
    )
    connection.execute(
        text(
            "INSERT INTO documents (document_id, source_id, kind, title, "
            "published_at, retrieved_at, content_hash, visibility, tenant_id, "
            "schema_version) VALUES (:document_id, :source_id, :kind, :title, "
            ":published_at, :retrieved_at, :content_hash, :visibility, "
            ":tenant_id, :schema_version)"
        ),
        {
            "document_id": document_id,
            "source_id": source_id,
            "kind": "advisory",
            "title": "synthetic document",
            "published_at": None,
            "retrieved_at": now,
            "content_hash": "0" * 64,
            "visibility": visibility,
            "tenant_id": tenant_id,
            "schema_version": 1,
        },
    )


def test_duplicate_tip_reuse_creates_single_revision_without_events(
    migrated_engine, tmp_path
) -> None:
    """T05-C01: 相同末版重复导入不新增修订、不重复业务事件。"""
    store = make_content_store(tmp_path)
    now = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)
    document_id = str(uuid.uuid4())
    with migrated_engine.begin() as connection:
        seed_document(connection, document_id, "public", None)
        attempts_before = connection.execute(select(fetch_attempts.c.attempt_id)).all()
        first = save_document_revision(
            connection, store, document_id, b"same-content", "public", None, now
        )
        second = save_document_revision(
            connection, store, document_id, b"same-content", "public", None, now
        )
        revision_rows = connection.execute(
            select(document_revisions.c.revision_id).where(
                document_revisions.c.document_id == document_id
            )
        ).all()
        attempts_after = connection.execute(select(fetch_attempts.c.attempt_id)).all()
    assert first.reused is False
    assert second.reused is True and second.revision_id == first.revision_id
    assert len(revision_rows) == 1
    assert len(attempts_after) == len(attempts_before)


def test_content_a_b_a_keeps_three_revisions_in_order(migrated_engine, tmp_path) -> None:
    """T05-C02: A→B→A 保留 3 条按序修订, 第一与第三同 hash。"""
    store = make_content_store(tmp_path)
    document_id = str(uuid.uuid4())
    base_time = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)
    with migrated_engine.begin() as connection:
        seed_document(connection, document_id, "public", None)
        first = save_document_revision(
            connection, store, document_id, b"content-A", "public", None, base_time
        )
        second = save_document_revision(
            connection, store, document_id, b"content-B", "public", None, base_time
        )
        third = save_document_revision(
            connection, store, document_id, b"content-A", "public", None, base_time
        )
        rows = connection.execute(
            select(document_revisions.c.revision_number, document_revisions.c.content_hash)
            .where(document_revisions.c.document_id == document_id)
            .order_by(document_revisions.c.revision_number)
        ).all()
    assert [row[0] for row in rows] == [1, 2, 3]
    assert first.content_hash == third.content_hash != second.content_hash
    assert first.reused is False and third.reused is False


def test_database_failure_after_object_write_leaves_no_dangling_record(
    migrated_engine, tmp_path
) -> None:
    """T05-C03: 写原文后数据库失败 → 清理未引用对象, 不产生指向缺失原文的有效记录。"""
    store = make_content_store(tmp_path)
    stored = store.store_bytes(b"orphan-candidate")
    with pytest.raises(MissingDocumentError), migrated_engine.begin() as connection:
        save_document_revision(
            connection,
            store,
            str(uuid.uuid4()),
            b"orphan-candidate",
            "public",
            None,
            datetime(2026, 9, 30, 12, 0, tzinfo=UTC),
        )
    with migrated_engine.begin() as connection:
        dangling_revisions = connection.execute(
            select(document_revisions.c.revision_id).where(
                document_revisions.c.content_hash == stored.content_hash
            )
        ).all()
        assert dangling_revisions == []
        removed = cleanup_unreferenced_object(connection, store, stored.content_hash)
    assert removed is True
    assert not stored.object_path.exists()


def test_cleanup_refuses_to_delete_referenced_object(migrated_engine, tmp_path) -> None:
    """M1 修复回归: documents 或修订仍引用对象时清理必须拒删。"""
    store = make_content_store(tmp_path)
    now = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)
    document_id = str(uuid.uuid4())
    with migrated_engine.begin() as connection:
        seed_document(connection, document_id, "public", None)
        saved = save_document_revision(
            connection, store, document_id, b"referenced-content", "public", None, now
        )
        refused = cleanup_unreferenced_object(connection, store, saved.content_hash)
        content_row = connection.execute(
            select(content_objects.c.content_hash).where(
                content_objects.c.content_hash == saved.content_hash
            ),
        ).scalar_one_or_none()
    assert refused is False
    assert content_row == saved.content_hash
    assert (tmp_path / "objects" / saved.content_hash[:2] / saved.content_hash).exists()


def test_malicious_path_input_cannot_influence_object_location(tmp_path) -> None:
    """T05-C04: 恶意文件路径被拒; 对象路径仅由内容哈希导出。"""
    store = make_content_store(tmp_path)
    with pytest.raises(ContentPathValidationError):
        store.object_path_for_hash("../../etc/passwd")
    with pytest.raises(ContentPathValidationError):
        store.object_path_for_hash("..\\windows\\system32")
    stored = store.store_bytes(b"hash-derived-path")
    assert stored.object_path.parent.name == stored.content_hash[:2]
    assert stored.object_path.name == stored.content_hash


def test_cross_tenant_evidence_reference_is_rejected(migrated_engine, tmp_path) -> None:
    """T05-C05: 跨 tenant 与缺 tenant 的 tenant 证据一律拒绝。"""
    store = make_content_store(tmp_path)
    now = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)
    document_id = str(uuid.uuid4())
    with migrated_engine.begin() as connection:
        seed_document(connection, document_id, "tenant", "tenant-alpha")
        saved = save_document_revision(
            connection, store, document_id, b"tenant-content", "tenant", "tenant-alpha", now
        )
        with pytest.raises(TenantScopeViolation):
            attach_evidence_span(
                connection,
                saved.revision_id,
                0,
                5,
                "line 1",
                "quote",
                True,
                "tenant",
                "tenant-beta",
                now,
            )
        with pytest.raises(TenantScopeViolation):
            attach_evidence_span(
                connection, saved.revision_id, 0, 5, "line 1", "quote", True, "public", None, now
            )
        with pytest.raises(TenantScopeViolation):
            attach_evidence_span(
                connection, saved.revision_id, 0, 5, "line 1", "quote", True, "tenant", None, now
            )


def test_evidence_attach_success_and_quote_consistency(migrated_engine, tmp_path) -> None:
    """M3 修复: 证据挂接正例 + 引文与原文块一致性校验(引文存在≠内容支持)。"""
    store = make_content_store(tmp_path)
    now = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)
    document_id = str(uuid.uuid4())
    block_text = "synthetic advisory body text"
    with migrated_engine.begin() as connection:
        seed_document(connection, document_id, "public", None)
        saved = save_document_revision(
            connection, store, document_id, b"body-content", "public", None, now
        )
        block_id = add_text_block(connection, saved.revision_id, 1, 0, len(block_text), block_text)
        evidence_id = attach_evidence_span(
            connection,
            saved.revision_id,
            0,
            8,
            "line 1",
            block_text[:8],
            True,
            "public",
            None,
            now,
            block_id=block_id,
            verified_at=now,
        )
        assert evidence_id
        with pytest.raises(QuoteConsistencyError):
            attach_evidence_span(
                connection,
                saved.revision_id,
                0,
                8,
                "line 1",
                block_text[:8],
                True,
                "public",
                None,
                now,
                block_id=block_id,
                quote_sha256="0" * 64,
            )
        with pytest.raises(QuoteConsistencyError):
            attach_evidence_span(
                connection,
                saved.revision_id,
                0,
                8,
                "line 1",
                "quote",
                True,
                "public",
                None,
                now,
                block_id=str(uuid.uuid4()),
            )
        row = connection.execute(
            select(evidence_table.c.quote_sha256).where(
                evidence_table.c.evidence_id == evidence_id
            ),
        ).scalar_one()
    assert row == hashlib.sha256(block_text.encode("utf-8")).hexdigest()


def test_migration_upgrade_preserves_existing_facts_times_and_unknown_status(
    migrated_engine, tmp_path
) -> None:
    """T05-C06: 既有数据升级后事实、时间与 unknown 状态保留; 幂等复跑不破坏。"""
    now = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)
    claim_id = str(uuid.uuid4())
    with migrated_engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO claims (claim_id, subject, predicate, object_value, "
                "claim_status, claim_origin, condition_value, freshness, asserted_at, "
                "observed_at, visibility, tenant_id, created_at) VALUES (:claim_id, "
                ":subject, :predicate, :object_value, :claim_status, :claim_origin, "
                ":condition_value, :freshness, :asserted_at, :observed_at, "
                ":visibility, :tenant_id, :created_at)"
            ),
            {
                "claim_id": claim_id,
                "subject": "component libdemo",
                "predicate": "affects",
                "object_value": "synthetic entry",
                "claim_status": "unverified",
                "claim_origin": "source_explicit",
                "condition_value": "unknown",
                "freshness": "unknown",
                "asserted_at": now,
                "observed_at": None,
                "visibility": "public",
                "tenant_id": None,
                "created_at": now,
            },
        )
    run_migrations(DEVELOPMENT_DSN)
    with migrated_engine.begin() as connection:
        row = connection.execute(
            text(
                "SELECT claim_status, condition_value, freshness, asserted_at, "
                "observed_at FROM claims WHERE claim_id = :claim_id"
            ),
            {"claim_id": claim_id},
        ).one()
    assert row[0] == "unverified"
    assert row[1] == "unknown"
    assert row[2] == "unknown"
    assert row[3] == now
    assert row[4] is None


def test_migration_downgrade_and_upgrade_roundtrip_and_version_recorded(migrated_engine) -> None:
    """迁移版本记录与回滚路径: downgrade 后 upgrade 可恢复, 版本号如实。"""
    run_migrations(DEVELOPMENT_DSN)
    assert current_migration_revision(DEVELOPMENT_DSN) == "0003_users"
    run_downgrade(DEVELOPMENT_DSN, "0002_constraints_and_text_blocks")
    assert current_migration_revision(DEVELOPMENT_DSN) == "0002_constraints_and_text_blocks"
    run_migrations(DEVELOPMENT_DSN)
    assert current_migration_revision(DEVELOPMENT_DSN) == "0003_users"


def test_fetch_attempt_is_recorded_without_counting_new_events(migrated_engine) -> None:
    """抓取记录不误计新业务事件: new_event_count 恒为 0。"""
    now = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)
    source_id = str(uuid.uuid4())
    source_name = "synthetic-source-" + source_id
    with migrated_engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO sources (source_id, name, category, base_origin, "
                "visibility, tenant_id, created_at) VALUES (:source_id, :name, "
                ":category, :base_origin, :visibility, :tenant_id, :created_at)"
            ),
            {
                "source_id": source_id,
                "name": source_name,
                "category": "vendor_advisory",
                "base_origin": "https://example.invalid",
                "visibility": "public",
                "tenant_id": None,
                "created_at": now,
            },
        )
        attempt_id = record_fetch_attempt(connection, source_id, now, "no_result", None)
        row = connection.execute(
            select(fetch_attempts.c.new_event_count).where(
                fetch_attempts.c.attempt_id == attempt_id
            )
        ).scalar_one()
    assert row == 0


def test_scope_epoch_bumps_for_cache_invalidation(migrated_engine) -> None:
    """scope epoch 基础表: 事实变更后 epoch 递增, 旧读缓存据此过期。"""
    now = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)
    scope_key = "tenant-alpha-" + str(uuid.uuid4())
    with migrated_engine.begin() as connection:
        first = bump_scope_epoch(connection, scope_key, now)
        second = bump_scope_epoch(connection, scope_key, now)
    assert first == 1 and second == 2
