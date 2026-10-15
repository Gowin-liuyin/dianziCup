"""0009真实旧结果升级后保持未知时点，不通过回填伪装新来源。"""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import text
from test_r02_schema_migration import empty_schema_engine as empty_schema_engine

from ai_intel.infrastructure.database import run_migrations


def test_0009_result_survives_forward_upgrade_with_unknown_provenance(empty_schema_engine):
    connection_url = empty_schema_engine.url.render_as_string(hide_password=False)
    run_migrations(connection_url, "0009_enrichment_results")
    event_id, result_id = str(uuid4()), str(uuid4())
    original_time = datetime(2026, 10, 1, tzinfo=UTC)
    with empty_schema_engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO events(event_id,event_type,title,scope_key,visibility,status,"
                "first_seen_at) VALUES (:id,'vulnerability','test legacy dimension','public',"
                "'public','active',:time)"
            ),
            {"id": event_id, "time": original_time},
        )
        connection.execute(
            text(
                "INSERT INTO enrichment_results(result_id,event_id,dimension,status,claim_ids,"
                "reference_ids,source_scope,input_fingerprint,recorded_at,is_current,error_code) "
                "VALUES (:id,:event,'epss','failed','[]','[]','[]',:fingerprint,:time,true,"
                "'timeout')"
            ),
            {"id": result_id, "event": event_id, "fingerprint": "a" * 64, "time": original_time},
        )
    run_migrations(connection_url)
    with empty_schema_engine.connect() as connection:
        row = (
            connection.execute(
                text("SELECT * FROM enrichment_results WHERE result_id=:id"), {"id": result_id}
            )
            .mappings()
            .one()
        )
        assert row["recorded_at"] == original_time
        assert row["status"] == "failed" and row["error_code"] == "timeout"
        assert all(
            row[name] is None
            for name in (
                "publication_key",
                "payload_sha256",
                "event_version",
                "observed_at",
                "source_version",
                "freshness",
            )
        )
