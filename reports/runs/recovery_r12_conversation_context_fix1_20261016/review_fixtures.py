"""Own fresh database and UUID schemas; no change to author tests or business code."""
from uuid import uuid4
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool
from sqlalchemy.schema import CreateSchema, DropSchema
from ai_intel.infrastructure.database import run_migrations
from ai_intel.knowledge.models import metadata
from ai_intel.answering.conversation_models import qa_conversations,qa_conversation_turns


@pytest.fixture
def conversation_database(isolated_test_database_url, request):
    url=make_url(isolated_test_database_url)
    assert url.database=='test_dianzi_r12_ctx_fix1_20261016' and url.host=='127.0.0.1' and url.port==25432
    schema='test_r12_fix1_'+uuid4().hex
    base=create_engine(url,poolclass=NullPool,hide_parameters=True,connect_args={'connect_timeout':3})
    with base.begin() as connection:
        connection.execute(CreateSchema(schema))
    try:
        scoped=url.update_query_dict({'options':f'-c search_path={schema},public -c statement_timeout=15000 -c lock_timeout=3000'})
        run_migrations(scoped.render_as_string(hide_password=False))
        engine=create_engine(scoped,poolclass=NullPool,hide_parameters=True,connect_args={'connect_timeout':3})
        try:
            with engine.begin() as connection:
                assert connection.scalar(text('SELECT current_schema()'))==schema
                metadata.create_all(connection,tables=[qa_conversations,qa_conversation_turns])
                if request.node.name in {
                    'test_pg_child_admission_verifies_saved_parent_hash',
                    'test_pg_corrupted_context_sha_does_not_become_a_valid_replay',
                    'test_pg_legacy_parent_identity_mismatch_fails_closed',
                }:
                    connection.execute(text('ALTER TABLE qa_conversation_turns DISABLE TRIGGER qa_conversation_turns_immutable'))
                    print('explicit_legacy_corruption_fault_injection:'+request.node.name)
            yield engine
        finally:
            engine.dispose()
    finally:
        assert schema.startswith('test_r12_fix1_') and schema.isidentifier()
        with base.begin() as connection:
            connection.execute(DropSchema(schema,cascade=True))
        base.dispose()
        print('review_owned_schema_removed:'+schema)


@pytest.fixture
def vector_database(isolated_test_database_url,tmp_path_factory):
    from ai_intel.infrastructure.content_store import ContentStore
    from test_r05_vector_persistence import load_legacy_0013_seed
    from sqlalchemy import select
    url=make_url(isolated_test_database_url)
    assert url.database=='test_dianzi_r12_ctx_fix1_20261016'
    schema='test_r05_fix1_'+uuid4().hex
    base=create_engine(url,poolclass=NullPool,hide_parameters=True)
    with base.begin() as connection:
        connection.execute(CreateSchema(schema))
    scoped=url.update_query_dict({'options':f'-c search_path={schema},public -c statement_timeout=15000 -c lock_timeout=3000'})
    engine=create_engine(scoped,poolclass=NullPool,hide_parameters=True)
    try:
        run_migrations(scoped.render_as_string(hide_password=False),'0013_revision_source_metadata')
        tables=load_legacy_0013_seed(engine,schema,ContentStore(tmp_path_factory.mktemp('review-vector-content')))
        with engine.connect() as connection:
            before=tuple(tuple(connection.execute(select(table).order_by(*table.primary_key.columns))) for table in tables)
        run_migrations(scoped.render_as_string(hide_password=False))
        with engine.connect() as connection:
            after=tuple(tuple(connection.execute(select(table).order_by(*table.primary_key.columns))) for table in tables)
        assert before==after and before
        yield engine
    finally:
        engine.dispose()
        with base.begin() as connection:
            connection.execute(DropSchema(schema,cascade=True))
        base.dispose()
        print('review_owned_schema_removed:'+schema)
