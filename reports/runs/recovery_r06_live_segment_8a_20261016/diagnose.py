"""Read terminal source metadata without payload or opaque token disclosure."""

from common import PRODUCT_SHA, verify_authorization, write

verify_authorization()

import json
import os
from sqlalchemy import create_engine, text

engine = create_engine(os.environ["DATABASE_URL"], hide_parameters=True, connect_args={"connect_timeout": 3, "options": "-c statement_timeout=3000"})
with engine.connect() as connection:
    connection.execute(text("SET TRANSACTION READ ONLY"))
    jobs = []
    for row in connection.execute(text("select j.job_id,j.status,j.attempt_count,j.created_at,j.started_at,j.finished_at,j.updated_at,j.lease_expires_at,j.error_code,p.payload from job_runs j join job_payloads p on p.job_id=j.job_id order by j.created_at,j.job_id")).mappings():
        value = {key: item for key, item in row.items() if key != "payload"}
        value["source_kind"] = json.loads(bytes(row["payload"]))["source_kind"]
        jobs.append(value)
    transitions = [dict(row) for row in connection.execute(text("select job_id,attempt_count,from_status,to_status,reason,changed_at from job_transitions order by transition_sequence")).mappings()]
    responses = [dict(row) for row in connection.execute(text("select source_kind,job_id,attempt_count,response_ordinal,observed_at,http_status,response_content_hash,response_size_bytes,parse_outcome,error_code from source_response_receipts order by observed_at,receipt_id")).mappings()]
engine.dispose()
write("diagnosis_receipt.json", {"product_sha": PRODUCT_SHA, "jobs": jobs, "transitions": transitions, "responses": responses, "payloads_or_cursor_values_recorded": False})
print(json.dumps({"running_jobs": [job for job in jobs if job["status"] == "running"], "response_sources": sorted({response["source_kind"] for response in responses})}, default=str))
