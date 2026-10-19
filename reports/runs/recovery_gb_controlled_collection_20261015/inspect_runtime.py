"""Read only resource checks; private material stays in captured memory."""

import json
import subprocess
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from zoneinfo import ZoneInfo

import redis
from sqlalchemy import create_engine, text

RUN = Path(__file__).resolve().parent
result = subprocess.run(["wsl", "-d", "Ubuntu-22.04", "-u", "root", "--exec", "cat", "/tmp/dianzi-r04-live-20261015/private/runtime_8f6bd9.json"], capture_output=True, text=True, check=True, timeout=10)
configuration = json.loads(result.stdout)
environment = configuration["environment"]
engine = create_engine(environment["DATABASE_URL"], connect_args={"connect_timeout": 3, "options": "-c statement_timeout=3000"})
with engine.connect() as connection:
    database = connection.scalar(text("select current_database()"))
    migrations = connection.execute(text("select version_num from alembic_version")).scalars().all()
    jobs = [dict(row) for row in connection.execute(text("select status,count(*) as count from job_runs group by status order by status")).mappings()]
    live_jobs = [dict(row) for row in connection.execute(text("select job_id,job_type,status,created_at,started_at from job_runs where status in ('queued','running','retry_wait')")).mappings()]
    columns = {name: connection.execute(text("select column_name from information_schema.columns where table_schema='public' and table_name=:name order by ordinal_position"), {"name": name}).scalars().all() for name in ("sources", "documents", "document_revisions", "fetch_attempts", "source_cursors", "source_page_receipts", "job_runs")}
    counts = {name: connection.scalar(text("select count(*) from " + name)) for name in ("events", "documents", "document_revisions", "evidence", "fetch_attempts", "source_page_receipts")}
    clients = [dict(row) for row in connection.execute(text("select application_name,state,count(*) as count from pg_stat_activity where datname=current_database() group by application_name,state")).mappings()]
parts = urlsplit(environment["REDIS_URL"])
redis_client = redis.Redis.from_url(urlunsplit(parts._replace(path="/12")), socket_timeout=3)
redis_state = {"candidate_database": 12, "key_count": redis_client.dbsize(), "client_databases": [int(item["db"]) for item in redis_client.client_list()]}
receipt = {"observed_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"), "environment_keys": sorted(environment), "database": database, "migrations": migrations, "jobs": jobs, "nonterminal_jobs": live_jobs, "columns": columns, "counts": counts, "database_clients": clients, "redis": redis_state}
(RUN / "resource_preflight.json").write_text(json.dumps(receipt, indent=2, default=str) + "\n", encoding="utf-8")
print(json.dumps({key: receipt[key] for key in ("observed_at", "database", "migrations", "jobs", "nonterminal_jobs", "counts", "database_clients", "redis")}))
engine.dispose()
