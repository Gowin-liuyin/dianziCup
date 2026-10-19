"""Upgrade independent fresh and seeded history databases using ordinary Alembic."""

import hashlib
import json

from review_runner import RUN, create_database, now
from sqlalchemy import MetaData, create_engine, inspect, text

from ai_intel.infrastructure.database import run_migrations

FIXTURE_TEXT = "Synthetic retained statement"
HEAD = "0019_aggregate_observations"


def forbidden_create_all(*arguments, **keywords):
    raise AssertionError("production upgrade must not invoke metadata.create_all")


def table_digest(connection, table_names):
    records = {}
    for table_name in table_names:
        rows = sorted(
            connection.exec_driver_sql(
                f'SELECT to_jsonb(record)::text FROM "{table_name}" record'
            ).scalars()
        )
        payload = json.dumps(rows, ensure_ascii=True, separators=(",", ":")).encode()
        records[table_name] = {
            "row_count": len(rows),
            "sha256": hashlib.sha256(payload).hexdigest(),
        }
    return records


def seed_history(connection):
    content_hash = hashlib.sha256(FIXTURE_TEXT.encode()).hexdigest()
    connection.exec_driver_sql("""
        INSERT INTO sources(source_id,name,category,base_origin,visibility,created_at)
        VALUES ('review-source','Independent synthetic retained source','structured_vulnerability',
                'https://example.invalid','public','2026-10-15T00:00:00Z');
    """)
    connection.execute(
        text("""
        INSERT INTO content_objects(content_hash,size_bytes,created_at)
        VALUES (:hash,:size,'2026-10-15T00:00:00Z')
    """),
        {"hash": content_hash, "size": len(FIXTURE_TEXT.encode())},
    )
    connection.execute(
        text("""
        INSERT INTO documents(document_id,source_id,kind,title,retrieved_at,content_hash,
                              visibility,schema_version)
        VALUES ('review-document','review-source','advisory',
                'Independent synthetic retained document',
                '2026-10-15T00:00:00Z',:hash,'public',1)
    """),
        {"hash": content_hash},
    )
    connection.execute(
        text("""
        INSERT INTO document_revisions(revision_id,document_id,revision_number,content_hash,
                created_at,is_current,visibility,parser_version,parse_status,canonical_uri)
        VALUES ('review-revision','review-document',1,:hash,'2026-10-15T00:00:00Z',true,
                'public','independent-fixture-1','parsed','https://example.invalid/retained')
    """),
        {"hash": content_hash},
    )
    connection.execute(
        text("""
        INSERT INTO text_blocks(block_id,revision_id,ordinal,start_offset,end_offset,
                                text_sha256,block_text,block_type)
        VALUES ('review-block','review-revision',1,0,:end,:hash,:quote,'paragraph')
    """),
        {"hash": content_hash, "end": len(FIXTURE_TEXT), "quote": FIXTURE_TEXT},
    )
    connection.execute(
        text("""
        INSERT INTO evidence(evidence_id,revision_id,start_offset,end_offset,locator,quote,
                supports_claim,visibility,created_at,block_id,quote_sha256,verified_at,coordinate_version)
        VALUES ('review-evidence','review-revision',0,:end,'offset:0-28',:quote,true,
                'public','2026-10-15T00:00:00Z','review-block',:hash,
                '2026-10-15T00:00:00Z','unicode-codepoint-v1')
    """),
        {"hash": content_hash, "end": len(FIXTURE_TEXT), "quote": FIXTURE_TEXT},
    )
    connection.exec_driver_sql("""
        INSERT INTO claims(claim_id,subject,predicate,object_value,claim_status,claim_origin,
                           condition_value,freshness,asserted_at,visibility,created_at)
        VALUES ('review-claim','synthetic-product','has_version','1.0','confirmed','source',
                'unknown','current','2026-10-15T00:00:00Z','public','2026-10-15T00:00:00Z');
        INSERT INTO claim_evidence(claim_id,evidence_id,support_kind,validation_status)
        VALUES ('review-claim','review-evidence','supports','validated');
        INSERT INTO users(user_id,username,password_hash,tenant_id,role,created_at)
        VALUES ('review-user','review-user','synthetic-unused-hash','review-tenant',
                'tenant_admin','2026-10-15T00:00:00Z');
        INSERT INTO events(event_id,event_type,title,scope_key,visibility,status,first_seen_at)
        VALUES ('review-event','advisory','Synthetic retained event','public','public','active',
                '2026-10-15T00:00:00Z');
        INSERT INTO job_runs(job_id,tenant_id,job_type,status,payload_ref,created_at,updated_at,
                             attempt_count,started_at,finished_at,result_ref)
        VALUES ('review-job','review-tenant','synthetic-source','succeeded','synthetic-retained',
                '2026-10-15T00:00:00Z','2026-10-15T00:01:00Z',1,
                '2026-10-15T00:00:00Z','2026-10-15T00:01:00Z','review-revision');
        INSERT INTO job_transitions(job_id,attempt_count,from_status,to_status,reason,changed_at)
        VALUES ('review-job',1,'queued','running','synthetic started','2026-10-15T00:00:00Z'),
               ('review-job',1,'running','succeeded','synthetic completed','2026-10-15T00:01:00Z');
        INSERT INTO job_payloads(job_id,payload,created_at)
        VALUES ('review-job',convert_to('synthetic retained payload','UTF8'),
                '2026-10-15T00:00:00Z');
        INSERT INTO outbox_events(event_id,job_id,topic,payload_ref,created_at,published_at)
        VALUES ('review-outbox','review-job','source-ingested','review-revision',
                '2026-10-15T00:01:00Z','2026-10-15T00:02:00Z');
        INSERT INTO source_cursors(source_id,stream_kind,cursor_json,last_successful_page,
                                   generation,watermark_published_at,updated_at)
        VALUES ('review-source','live','{"page":3,"synthetic":true}',3,2,
                '2026-10-14T23:00:00Z','2026-10-15T00:01:00Z');
    """)


def write_json(filename, record):
    (RUN / filename).write_text(json.dumps(record, indent=2), encoding="utf-8")


def main():
    MetaData.create_all = forbidden_create_all
    receipts = []
    for suffix in ("fresh", "hist"):
        started = now()
        url = create_database(suffix)
        database_url = url.render_as_string(hide_password=False)
        engine = create_engine(url, hide_parameters=True)
        if suffix == "hist":
            run_migrations(database_url, "0016_source_response_receipts")
            with engine.begin() as connection:
                seed_history(connection)
            with engine.connect() as connection:
                names = sorted(set(inspect(connection).get_table_names()) - {"alembic_version"})
                assert len(names) == 37
                before = table_digest(connection, names)
            write_json("history_before_0016.json", before)
        run_migrations(database_url)
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == HEAD
            assert connection.scalar(text("SELECT current_database()")) == url.database
            if suffix == "hist":
                after = table_digest(connection, names)
                write_json("history_after_0019.json", after)
                assert before == after
            receipts.append(
                {
                    "database": url.database,
                    "started_at": started,
                    "finished_at": now(),
                    "exit_code": 0,
                    "postgresql_version": connection.scalar(text("SHOW server_version")),
                    "from_revision": "empty"
                    if suffix == "fresh"
                    else "0016_source_response_receipts",
                    "to_revision": HEAD,
                    "method": "ordinary run_migrations/Alembic upgrade head",
                    "metadata_create_all": "forbidden",
                    "old_tables_unchanged": 37 if suffix == "hist" else None,
                }
            )
        engine.dispose()
        write_json("database_receipts.json", receipts)
        print(json.dumps(receipts[-1]), flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as failure:
        print("independent preparation failed: " + type(failure).__name__)
        print("sqlstate=" + str(getattr(getattr(failure, "orig", None), "sqlstate", None)))
        print(
            "ddl_diagnostic="
            + str(
                getattr(
                    getattr(getattr(failure, "orig", None), "diag", None), "message_primary", None
                )
            )
        )
        raise SystemExit(2) from None
