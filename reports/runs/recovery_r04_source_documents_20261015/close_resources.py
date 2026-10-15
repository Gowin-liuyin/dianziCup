"""Inspect only this task's isolated database and its private test credential."""

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

private = json.loads(Path("/tmp/dianzi-r04_source_documents_20261015/connection.json").read_bytes())
url = make_url(private["TEST_DATABASE_URL"])
assert url.database == "test_dianzi_r04_source_documents_20261015"
engine = create_engine(url)
with engine.connect() as connection:
    active = connection.scalar(text("SELECT count(*) FROM pg_stat_activity WHERE datname=:name "
        "AND pid<>pg_backend_pid() AND state<>'idle'"), {"name":url.database})
    schemas = connection.scalar(text("SELECT count(*) FROM pg_namespace "
        "WHERE nspname LIKE 'test_r04_source_documents_%' OR nspname LIKE 'test_r02_schema_%'"))
engine.dispose()
assert active == 0 and schemas == 0
run = Path(__file__).parent
password = url.password or ""
fragments = {password[index:index+8].encode() for index in range(max(0,len(password)-7))}
hits = []
for path in run.iterdir():
    if path.suffix not in {".json", ".log", ".xml", ".py", ".md"}:
        continue
    body = path.read_bytes()
    if (private["TEST_DATABASE_URL"].encode() in body or password.encode() in body
        or any(fragment in body for fragment in fragments)):
        hits.append(path.name)
assert not hits
receipt = {"closed_at":datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
    "database_name":url.database,"active_other_connections":active,
    "remaining_owned_test_schemas":schemas,"actual_owned_test_credential_matches":hits,
    "preserved": "database and root-only private connection retained for independent review",
    "services": "none started by this work package"}
(run/"resource_close.json").write_text(json.dumps(receipt,indent=2)+"\n",encoding="utf-8")
print(json.dumps(receipt))
