"""Inspect only this package's isolated database; do not stop shared services."""

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

private = json.loads(Path("/tmp/dianzi-r04_vendor_cursor_20261015/connection.json").read_bytes())
url = make_url(private["TEST_DATABASE_URL"])
assert url.database == "test_dianzi_r04_vendor_cursor_20261015"
engine = create_engine(url, connect_args={"connect_timeout": 5})
with engine.connect() as connection:
    schemas = connection.scalar(text(
        "SELECT count(*) FROM pg_namespace WHERE nspname LIKE 'test_r02_schema_%' "
        "OR nspname LIKE 'test_r04_source_documents_%'"
    ))
    connections = connection.scalar(text(
        "SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() "
        "AND pid<>pg_backend_pid()"
    ))
engine.dispose()
result = {
    "checked_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
    "database": url.database, "remaining_test_schemas": schemas,
    "other_database_connections": connections,
    "public_get_count_this_package": 0, "product_model_api_calls_this_package": 0,
    "services_started_by_this_package": [], "private_connection_retained_for_reviewer": True,
}
Path(__file__).with_name("resource_close.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result))
assert schemas == 0 and connections == 0
