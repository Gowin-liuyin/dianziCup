"""独立构造 NULL租户、完整行篡改、影子schema、限流和历史回滚场景。"""

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from tests.integration import test_recovery_forward_migrations_0023_0026_pg as pg
from review_plugin import controlled_test_url

RUN = Path(__file__).resolve().parent/'pg_independent'
RUN.mkdir(exist_ok=True)
pg.RUN = RUN
pg.MARKER = 'recovery_forward_migrations_review1_independent_20261016:'
pg.controlled_test_url = controlled_test_url
database = pg.database
register_credentials = pg.register_credentials
pytestmark = pytest.mark.real_pg


def test_null_tenant_scope_and_immediate_validation(database):
    with database.engine.begin() as connection:
        conversation = pg.insert_conversation(connection, tenant=None)
        answer = pg.insert_answer(connection, tenant=None)
        turn = pg.insert_turn(connection, conversation, answer, tenant=None)
        connection.execute(text('UPDATE qa_conversations SET active_turn_id=:turn,version=1 WHERE conversation_id=:id'), {'turn':turn,'id':conversation})
        connection.execute(text('SET CONSTRAINTS ALL IMMEDIATE'))
    with pytest.raises(IntegrityError) as failure, database.engine.begin() as connection:
        connection.execute(text('UPDATE grounded_answers SET tenant_id=:tenant WHERE answer_id=:id'), {'tenant':'tenant-a','id':answer})
        connection.execute(text('SET CONSTRAINTS ALL IMMEDIATE'))
    assert pg.postgres_error_code(failure.value)=='23514'
    with database.engine.connect() as connection:
        assert connection.scalar(text('SELECT tenant_id IS NULL FROM grounded_answers WHERE answer_id=:id'), {'id':answer}) is True


def test_schema_shadow_cannot_replace_workflow_or_owner_authority(database):
    shadow=database.schema+'_shadow'
    with database.engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{shadow}"'))
        connection.execute(text(f"COMMENT ON SCHEMA \"{shadow}\" IS '{database.marker}:shadow'"))
        connection.execute(text(f'CREATE TABLE "{shadow}".enrichment_workflows AS SELECT * FROM enrichment_workflows'))
        connection.execute(text(f'UPDATE "{shadow}".enrichment_workflows SET input_fingerprint=:digest'), {'digest':'f'*64})
        connection.execute(text(f'CREATE TABLE "{shadow}".qa_conversations AS SELECT * FROM qa_conversations WHERE false'))
        connection.execute(text(f'CREATE TABLE "{shadow}".qa_conversation_turns AS SELECT * FROM qa_conversation_turns WHERE false'))
        connection.execute(text(f'CREATE TABLE "{shadow}".grounded_answers AS SELECT * FROM grounded_answers WHERE false'))
        conversation=pg.insert_conversation(connection)
        answer=pg.insert_answer(connection)
        pg.insert_turn(connection,conversation,answer)
    payload=json.loads(pg.audit_payload('independent-shadow'))
    payload['input_fingerprint']='f'*64
    statement=pg.AUDIT_UPDATE.replace('UPDATE enrichment_job_steps',f'UPDATE "{database.schema}".enrichment_job_steps')
    with pytest.raises(IntegrityError) as failure, database.engine.begin() as connection:
        connection.execute(text(f'SET LOCAL search_path="{shadow}",public'))
        connection.execute(text(statement), {'payload':json.dumps(payload),'now':pg.NOW,'trace':pg.MODEL_TRACE})
    assert pg.postgres_error_code(failure.value)=='23514'
    with pytest.raises(IntegrityError) as failure, database.engine.begin() as connection:
        connection.execute(text(f'SET LOCAL search_path="{shadow}",public'))
        connection.execute(text(f'UPDATE "{database.schema}".qa_conversations SET user_id=:owner WHERE conversation_id=:id'), {'owner':'old-owner-b','id':conversation})
    assert pg.postgres_error_code(failure.value)=='23514'


def test_concurrent_full_row_turn_and_batch_tamper_is_rejected(database):
    payload=b'independent committed projection bytes'
    batch=str(uuid4())
    with database.engine.begin() as connection:
        conversation=pg.insert_conversation(connection)
        answer=pg.insert_answer(connection)
        turn=pg.insert_turn(connection,conversation,answer)
        connection.execute(text("INSERT INTO graph_projection_batches VALUES(:batch,'ns','part','gen','event',1,'snapshot',:digest,:payload,:now)"), {'batch':batch,'digest':hashlib.sha256(payload).hexdigest(),'payload':payload,'now':pg.NOW})
    barrier=Barrier(4)
    statements=[
        ('UPDATE qa_conversation_turns SET admitted_at=admitted_at WHERE turn_id=:id',turn),
        ('DELETE FROM qa_conversation_turns WHERE turn_id=:id',turn),
        ('UPDATE graph_projection_batches SET captured_at=captured_at WHERE batch_id=:id',batch),
        ('DELETE FROM graph_projection_batches WHERE batch_id=:id',batch),
    ]
    def attempt(statement):
        try:
            with database.engine.begin() as connection:
                barrier.wait(timeout=10)
                connection.execute(text(statement[0]), {'id':statement[1]})
            return 'committed'
        except IntegrityError as failure:
            return pg.postgres_error_code(failure)
    with ThreadPoolExecutor(max_workers=4) as executor:
        results=list(executor.map(attempt,statements))
    assert results==['23514']*4
    with database.engine.connect() as connection:
        assert connection.scalar(text('SELECT payload FROM graph_projection_batches WHERE batch_id=:id'),{'id':batch})==payload
        assert connection.scalar(text('SELECT count(*) FROM qa_conversation_turns WHERE turn_id=:id'),{'id':turn})==1


def test_ask_last_slot_uses_atomic_constraint_and_keeps_failed_tx_unchanged(database):
    parameters=pg.key_parameters()
    with database.engine.begin() as connection:
        connection.execute(text(pg.KEY_INSERT),parameters)
        connection.execute(text("INSERT INTO api_key_rate_buckets VALUES(:id,'ask',:now,9)"), {'id':parameters['key'],'now':pg.NOW})
    sql="UPDATE api_key_rate_buckets SET request_count=request_count+1 WHERE key_id=:id AND operation='ask'"
    assert pg.concurrent_codes(database.engine,((sql,{'id':parameters['key']}),(sql,{'id':parameters['key']})))==['23514','committed']
    with pytest.raises(IntegrityError), database.engine.begin() as connection:
        connection.execute(text('UPDATE api_keys SET revoked_at=:now,version=2 WHERE key_id=:id'), {'now':pg.NOW,'id':parameters['key']})
        connection.execute(text(sql), {'id':parameters['key']})
    with database.engine.connect() as connection:
        assert connection.execute(text("SELECT k.revoked_at,k.version,b.request_count FROM api_keys k JOIN api_key_rate_buckets b USING(key_id) WHERE key_id=:id"),{'id':parameters['key']}).one()==(None,1,10)


def test_dst_exact_maximum_and_over_limit_in_same_timezone(database):
    issued=datetime(2026,8,15,tzinfo=UTC)
    with database.engine.begin() as connection:
        connection.execute(text("SET LOCAL TIME ZONE 'America/New_York'"))
        connection.execute(text(pg.KEY_INSERT), {**pg.key_parameters(),'issued':issued,'expires':issued+timedelta(hours=2160)})
    with pytest.raises(IntegrityError) as failure, database.engine.begin() as connection:
        connection.execute(text("SET LOCAL TIME ZONE 'America/New_York'"))
        connection.execute(text(pg.KEY_INSERT), {**pg.key_parameters(),'issued':issued,'expires':issued+timedelta(hours=2160,microseconds=1)})
    assert pg.postgres_error_code(failure.value)=='23514'


def test_failed_forward_upgrade_preserves_populated_history_and_restart_retry(database):
    schema=database.schema+'_rollback'
    rollback=pg.owned_engine(database.url,schema)
    with database.engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        connection.execute(text(f"COMMENT ON SCHEMA \"{schema}\" IS '{database.marker}:rollback'"))
    try:
        pg.upgrade(database.url,schema,'0022_sbom_sidecars','independent_rollback_0022')
        pg.seed_0022_history(rollback)
        reflector=inspect(rollback)
        tables=sorted(set(reflector.get_table_names(schema=schema))-{'alembic_version'})
        columns={t:tuple(c['name'] for c in reflector.get_columns(t,schema=schema)) for t in tables}
        before=pg.schema_rows(rollback,schema,columns)
        with rollback.begin() as connection:
            connection.execute(text('CREATE TABLE api_keys(marker TEXT PRIMARY KEY)'))
            connection.execute(text("INSERT INTO api_keys VALUES('independent-conflict')"))
        pg.upgrade(database.url,schema,pg.HEAD,'independent_expected_rollback',fails=True)
        after_failure=pg.schema_rows(rollback,schema,columns)
        assert before==after_failure
        with rollback.connect() as connection:
            assert connection.scalar(text(f'SELECT version_num FROM "{schema}".alembic_version'))=='0022_sbom_sidecars'
            assert connection.scalar(text('SELECT marker FROM api_keys'))=='independent-conflict'
        with rollback.begin() as connection:
            connection.execute(text('DROP TABLE api_keys'))
        rollback.dispose()
        pg.upgrade(database.url,schema,pg.HEAD,'independent_forward_retry')
        fresh=pg.owned_engine(database.url,schema)
        try:
            after_retry=pg.schema_rows(fresh,schema,columns)
            assert before==after_retry
            (RUN/'populated_rollback_history.json').write_text(json.dumps({'before':before,'after_failed_upgrade':after_failure,'after_restart_retry':after_retry},indent=2)+'\n',encoding='utf-8',newline='\n')
        finally:
            fresh.dispose()
    finally:
        rollback.dispose()
