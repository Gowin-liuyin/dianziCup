"""Independently verify immutable synthetic history without persisting a mutation."""
import hashlib
import json
import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.pool import NullPool

configured = make_url(os.environ["TEST_DATABASE_URL"])
assert (configured.host, configured.port, configured.database) == ("127.0.0.1", 25432, "test_dianzi_r17_real_review1_20261016")
assert os.environ["DIANZI_TEST_RUN_ID"] == "r17_real_review1_20261016"
payload = json.loads(sys.argv[1])
engine = create_engine(configured, hide_parameters=True, poolclass=NullPool, connect_args={"connect_timeout": 5, "options": "-c statement_timeout=5000 -c lock_timeout=3000"})
try:
    with engine.connect() as connection:
        rows = connection.execute(text("SELECT snapshot_id,snapshot_number,previous_snapshot_id,raw_input,raw_input_sha256,canonical_payload FROM asset_snapshots WHERE asset_id=:asset_id ORDER BY snapshot_number"), {"asset_id": payload["asset_id"]}).mappings().all()
        assert len(rows) == 3
        history = []
        for number, row in enumerate(rows, 1):
            assert row["snapshot_number"] == number
            assert hashlib.sha256(bytes(row["raw_input"])).hexdigest() == payload["raw_hashes"][number - 1] == row["raw_input_sha256"]
            assert row["previous_snapshot_id"] == (None if number == 1 else rows[number - 2]["snapshot_id"])
            history.append({"snapshot_id": row["snapshot_id"], "snapshot_number": number, "raw_sha256": row["raw_input_sha256"], "payload_sha256": hashlib.sha256(json.dumps(row["canonical_payload"], sort_keys=True, ensure_ascii=False).encode()).hexdigest()})
        current = connection.scalar(text("SELECT current_snapshot_id FROM assets WHERE asset_id=:asset_id"), {"asset_id": payload["asset_id"]})
        assert current == rows[-1]["snapshot_id"]
    mutations = []
    for table, operation in [("asset_snapshots", "update"), ("asset_snapshots", "delete"), ("asset_snapshot_sbom_sidecars", "update"), ("asset_snapshot_sbom_sidecars", "delete")]:
        with engine.connect() as connection:
            transaction = connection.begin()
            code = None
            try:
                statement = f"UPDATE {table} SET canonical_payload=canonical_payload WHERE snapshot_id=:snapshot_id" if operation == "update" else f"DELETE FROM {table} WHERE snapshot_id=:snapshot_id"
                connection.execute(text(statement), {"snapshot_id": rows[0]["snapshot_id"]})
            except DBAPIError as failure:
                code = failure.orig.sqlstate
            finally:
                transaction.rollback()
            assert code == "23514", (table, operation, code)
            mutations.append({"table": table, "operation": operation, "sqlstate": code, "always_rolled_back": True})
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT current_snapshot_id FROM assets WHERE asset_id=:asset_id"), {"asset_id": payload["asset_id"]}) == current
        assert connection.scalar(text("SELECT count(*) FROM asset_snapshots WHERE asset_id=:asset_id"), {"asset_id": payload["asset_id"]}) == 3
    print(json.dumps({"history": history, "current_snapshot_id": current, "mutation_rejections": mutations}))
finally:
    engine.dispose()
