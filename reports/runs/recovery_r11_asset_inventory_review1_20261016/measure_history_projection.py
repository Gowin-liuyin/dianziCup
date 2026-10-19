"""Record the unnecessary private bytea projection without exporting any raw content."""

import json
import subprocess

from ai_intel.assets.inventory import InventoryService
from ai_intel.assets.inventory_models import asset_snapshots
from ai_intel.domain.access import AccessScope, Role
from review_runner import RUN, now
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

config = json.loads(
    subprocess.check_output(
        [
            "wsl",
            "-d",
            "Ubuntu-22.04",
            "-u",
            "root",
            "--exec",
            "cat",
            "/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json",
        ]
    )
)
url = make_url(config["TEST_DATABASE_URL"])
assert url.host in {"127.0.0.1", "localhost"} and url.port == 25432
database = json.loads((RUN / "database_receipt.json").read_text())["database"]
assert database.startswith("test_dianzi_r11_inventory_review1_")
engine = create_engine(
    url.set(drivername="postgresql+psycopg", database=database, query={}),
    hide_parameters=True,
)
with engine.connect() as connection:
    row = connection.execute(
        select(
            asset_snapshots.c.asset_id,
            asset_snapshots.c.tenant_id,
            asset_snapshots.c.actor_user_id,
            func.octet_length(asset_snapshots.c.raw_input).label("raw_bytes"),
        )
        .order_by(func.octet_length(asset_snapshots.c.raw_input).desc())
        .limit(1)
    ).one()
trace = []


def observe(connection, cursor, statement, parameters, context, executemany):
    if "FROM asset_snapshots" in statement:
        trace.append(
            {
                "selects_raw_bytea": "asset_snapshots.raw_input," in statement,
                "selects_canonical_payload": "asset_snapshots.canonical_payload"
                in statement,
            }
        )


event.listen(engine, "before_cursor_execute", observe)
with Session(engine) as session:
    response = InventoryService(
        session,
        AccessScope.for_authenticated_user(
            row.actor_user_id, row.tenant_id, Role.TENANT_ADMIN
        ),
    ).list_snapshots(row.asset_id, limit=1)
event.remove(engine, "before_cursor_execute", observe)
response_json = response.model_dump_json()
receipt = {
    "recorded_at": now(),
    "input_kind": "existing_owned_synthetic_one_mib_fixture",
    "raw_bytes_on_selected_snapshot": row.raw_bytes,
    "queries": trace,
    "response_bytes": len(response_json.encode()),
    "response_has_raw_input_field": "raw_input" in response_json,
    "history_items": len(response.items),
    "classification": "P3_nonblocking_unnecessary_private_bytea_fetch",
    "minimal_fix": "Select only snapshot_number and canonical_payload for history pages",
}
(RUN / "history_projection_debt.json").write_text(
    json.dumps(receipt, indent=2), encoding="utf-8"
)
print(json.dumps(receipt), flush=True)
engine.dispose()
