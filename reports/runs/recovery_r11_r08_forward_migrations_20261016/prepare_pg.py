"""Prove ordinary forward upgrades on fresh, exclusively owned test databases."""

import hashlib
import json
import sys

from run_checks import ROOT, RUN, RUN_ID, approved_test_url, create_test_database, now
from sqlalchemy import MetaData, create_engine, inspect, text

sys.path.insert(0, str(ROOT / "backend/src"))
from ai_intel.infrastructure.database import run_migrations


def forbidden_create_all(*arguments, **keywords):
    raise AssertionError("runtime metadata.create_all is not a migration")


def old_rows(connection, table_names):
    result = {}
    for name in table_names:
        rows = connection.execute(text(f'SELECT to_jsonb(t)::text FROM "{name}" t')).scalars()
        canonical = json.dumps(sorted(rows), ensure_ascii=True).encode()
        result[name] = {
            "rows": len(json.loads(canonical)),
            "sha256": hashlib.sha256(canonical).hexdigest(),
        }
    return result


def seed_0016(connection):
    connection.exec_driver_sql("""
        INSERT INTO sources(source_id,name,category,base_origin,visibility,created_at)
        VALUES ('migration-source','Synthetic migration source','advisory',
                'https://example.invalid','public','2026-10-16T00:00:00Z');
        INSERT INTO content_objects(content_hash,size_bytes,created_at)
        VALUES (repeat('a',64),14,'2026-10-16T00:00:00Z');
        INSERT INTO documents(document_id,source_id,kind,title,retrieved_at,content_hash,
                              visibility,schema_version)
        VALUES ('migration-document','migration-source','advisory','Synthetic retained document',
                '2026-10-16T00:00:00Z',repeat('a',64),'public',1);
        INSERT INTO document_revisions(revision_id,document_id,revision_number,content_hash,
                                       created_at,is_current,visibility)
        VALUES ('migration-revision','migration-document',1,repeat('a',64),
                '2026-10-16T00:00:00Z',true,'public');
        INSERT INTO evidence(evidence_id,revision_id,start_offset,end_offset,locator,quote,
                             supports_claim,visibility,created_at)
        VALUES ('migration-evidence','migration-revision',0,14,'offset:0-14','Synthetic fact',
                true,'public','2026-10-16T00:00:00Z');
        INSERT INTO claims(claim_id,subject,predicate,object_value,claim_status,claim_origin,
                           condition_value,freshness,asserted_at,visibility,created_at)
        VALUES ('migration-claim','synthetic-product','has_version','1.0','confirmed','source',
                'unknown','current','2026-10-16T00:00:00Z','public','2026-10-16T00:00:00Z');
        INSERT INTO users(user_id,username,password_hash,tenant_id,role,created_at)
        VALUES ('migration-user','migration-user','synthetic-unused-hash','migration-tenant',
                'tenant_admin','2026-10-16T00:00:00Z');
        INSERT INTO job_runs(job_id,tenant_id,job_type,status,payload_ref,created_at,updated_at)
        VALUES ('migration-job','migration-tenant','synthetic-import','succeeded',
                'synthetic-retained','2026-10-16T00:00:00Z','2026-10-16T00:00:00Z');
        INSERT INTO job_transitions(job_id,attempt_count,from_status,to_status,reason,changed_at)
        VALUES ('migration-job',1,'running','succeeded','synthetic retained transition',
                '2026-10-16T00:00:00Z');
        INSERT INTO job_payloads(job_id,payload,created_at)
        VALUES ('migration-job',convert_to('synthetic retained payload','UTF8'),
                '2026-10-16T00:00:00Z');
        INSERT INTO source_cursors(source_id,stream_kind,cursor_json,last_successful_page,
                                   generation,updated_at)
        VALUES ('migration-source','live','{"page":7,"synthetic":true}',7,2,
                '2026-10-16T00:00:00Z');
    """)


def main():
    parsed = approved_test_url()
    MetaData.create_all = forbidden_create_all
    receipt_path = RUN / "database_receipts.json"
    receipts = json.loads(receipt_path.read_text()) if receipt_path.exists() else []
    for suffix in sys.argv[1:] or ("empty", "retained"):
        database_name = "test_dianzi_" + RUN_ID + "_" + suffix
        started = now()
        database_url = create_test_database(parsed, database_name)
        engine = create_engine(database_url, hide_parameters=True)
        retained = suffix.startswith("hist") or suffix.startswith("retained")
        if retained:
            run_migrations(database_url, "0016")
            with engine.begin() as connection:
                seed_0016(connection)
            with engine.connect() as connection:
                tables = sorted(set(inspect(connection).get_table_names()) - {"alembic_version"})
                before = old_rows(connection, tables)
            (RUN / "retained_before.json").write_text(
                json.dumps(before, indent=2), encoding="utf-8"
            )
            (RUN / f"retained_{suffix}_before.json").write_text(
                json.dumps(before, indent=2), encoding="utf-8"
            )
        run_migrations(database_url)
        with engine.connect() as connection:
            revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
            assert revision == "0019_aggregate_observations"
            if retained:
                after = old_rows(connection, tables)
                assert before == after
                (RUN / "retained_after.json").write_text(
                    json.dumps(after, indent=2), encoding="utf-8"
                )
                (RUN / f"retained_{suffix}_after.json").write_text(
                    json.dumps(after, indent=2), encoding="utf-8"
                )
            receipts.append(
                {
                    "database": database_name,
                    "started_at": started,
                    "finished_at": now(),
                    "exit_code": 0,
                    "from_revision": "empty" if not retained else "0016_source_response_receipts",
                    "revision": revision,
                    "postgresql_version": connection.scalar(text("SHOW server_version")),
                    "migration_method": "run_migrations ordinary Alembic upgrade head",
                    "metadata_create_all": "forbidden by assertion",
                    "old_tables_unchanged": len(tables) if retained else None,
                }
            )
        engine.dispose()
        (RUN / "database_receipts.json").write_text(
            json.dumps(receipts, indent=2), encoding="utf-8"
        )
        print(json.dumps(receipts[-1]), flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as failure:
        print("isolated forward migration failed; exception_type=" + type(failure).__name__)
        print("safe_sqlstate=" + str(getattr(getattr(failure, "orig", None), "sqlstate", None)))
        diagnostic = getattr(
            getattr(getattr(failure, "orig", None), "diag", None), "message_primary", None
        )
        print("safe_ddl_diagnostic=" + str(diagnostic))
        raise SystemExit(2) from None
