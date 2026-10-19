"""Read public receipts and bounded PG counters without changing collection state."""

from common import RUN, verify_authorization, write

verify_authorization()

import json
import os
from sqlalchemy import create_engine, text

engine = create_engine(os.environ["DATABASE_URL"], hide_parameters=True, connect_args={"connect_timeout": 3, "options": "-c statement_timeout=3000"})
with engine.connect() as connection:
    connection.execute(text("SET TRANSACTION READ ONLY"))
    counts = dict(connection.execute(text("select (select count(*) from job_runs where job_type='collect_public_source_page') source_jobs,(select count(*) from fetch_attempts) saved_http_receipts,(select count(*) from documents) documents,(select count(*) from document_revisions) revisions,(select count(*) from evidence) evidence")).mappings().one())
engine.dispose()
result = {"runtime_start": json.loads((RUN / "runtime_start.json").read_text()), "runtime_heartbeat": json.loads((RUN / "runtime_heartbeat.json").read_text()), "ended": (RUN / "runtime_end.json").exists(), "counts": counts}
write("status_snapshot.json", result)
print(json.dumps({"ended": result["ended"], "counts": counts}))
