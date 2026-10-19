"""Finite actions against this browser run's owned synthetic PostgreSQL database."""

import hashlib
import json
import os
import sys
import time
from datetime import UTC, datetime

from sqlalchemy import create_engine, select, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool

from ai_intel.api.auth_state import auth_sessions
from ai_intel.assets.inventory_models import asset_snapshots
from ai_intel.knowledge.models import users


def execute(action, payload):
    configured = make_url(os.environ["TEST_DATABASE_URL"])
    assert configured.database == "test_dianzi_r17_real_review1_20261016"
    assert configured.host == "127.0.0.1" and configured.port == 25432
    assert os.environ["DIANZI_TEST_RUN_ID"] == "r17_real_review1_20261016"
    engine = create_engine(configured, hide_parameters=True, poolclass=NullPool, connect_args={"connect_timeout": 5, "options": "-c statement_timeout=5000 -c lock_timeout=3000"})
    try:
        with engine.begin() as connection:
            if action == "verify-upload":
                row = connection.execute(select(asset_snapshots).where(asset_snapshots.c.snapshot_id == payload["snapshot_id"])).mappings().one()
                digest = hashlib.sha256(bytes(row["raw_input"])).hexdigest()
                assert digest == payload["raw_sha256"]
                return {"raw_sha256": digest, "snapshot_id": row["snapshot_id"], "snapshot_number": row["snapshot_number"], "migration": connection.scalar(text("SELECT version_num FROM alembic_version")), "public_schema": connection.scalar(text("SELECT current_schema()"))}
            if action in {"revoke-read", "revoke-session"}:
                actor = connection.execute(select(users).where(users.c.username == payload["username"])).mappings().one()
                assert actor["username"].startswith("r17-synthetic-browser-")
                if action == "revoke-read":
                    connection.execute(update(users).where(users.c.user_id == actor["user_id"]).values(role="viewer"))
                else:
                    connection.execute(update(auth_sessions).where(auth_sessions.c.user_id == actor["user_id"]).values(revoked_at=datetime.now(UTC)))
                return {"action": action, "actor_count": 1}
            if action == "sidecar-unavailable":
                connection.exec_driver_sql("ALTER TABLE asset_snapshot_sbom_sidecars RENAME TO r17_owned_unavailable_sbom_sidecars")
                return {"action": action, "restoration": "required"}
            if action == "sidecar-restore":
                connection.exec_driver_sql("ALTER TABLE r17_owned_unavailable_sbom_sidecars RENAME TO asset_snapshot_sbom_sidecars")
                return {"action": action, "restoration": "complete"}
            if action == "sidecar-delay":
                connection.exec_driver_sql("LOCK TABLE asset_snapshot_sbom_sidecars IN ACCESS EXCLUSIVE MODE")
                print(json.dumps({"locked": True}), flush=True)
                time.sleep(3)
                return {"action": action, "restoration": "complete"}
            raise ValueError("unsupported owned action")
    finally:
        engine.dispose()


if __name__ == "__main__":
    try:
        print(json.dumps(execute(sys.argv[1], json.loads(sys.argv[2]))))
    except Exception as failure:
        print(json.dumps({"error_type": type(failure).__name__}), file=sys.stderr)
        raise SystemExit(1) from None
