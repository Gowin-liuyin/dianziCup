"""Clean only orphaned schemas in this review's exact marked test database."""

import json
import re

from sqlalchemy import create_engine, text
from sqlalchemy.schema import DropSchema

from review_runner import DATABASE, MARKER, RUN, now, resources

url, _resource = resources()
engine = create_engine(url.set(database=DATABASE), connect_args={"connect_timeout": 5})
cleaned = []
try:
    with engine.begin() as connection:
        assert connection.execute(text("SELECT current_database(),current_user")).one() == (DATABASE, url.username)
        row = connection.execute(text("SELECT pg_get_userbyid(datdba),shobj_description(oid,'pg_database') FROM pg_database WHERE datname=:name"), {"name": DATABASE}).one()
        assert row == (url.username, MARKER)
        schemas = connection.execute(text("SELECT nspname,pg_get_userbyid(nspowner) FROM pg_namespace WHERE nspname LIKE :prefix"), {"prefix": "test_r10r1f2_%"}).all()
        for schema, owner in schemas:
            assert owner == url.username and re.fullmatch("test_r10r1f2_[0-9a-f]{32}", schema)
            connection.execute(DropSchema(schema, cascade=True))
            cleaned.append(schema)
    result = {"observed_at": now(), "database": DATABASE, "database_identity_and_owner_marker_matched": True,
              "cleaned_schema_names": cleaned, "cleaned_count": len(cleaned), "scope": "this review orphaned schemas only; no backend/session termination"}
    (RUN / "owned_pg_cleanup_receipt.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"cleaned_owned_schemas": len(cleaned)}))
finally:
    engine.dispose()
