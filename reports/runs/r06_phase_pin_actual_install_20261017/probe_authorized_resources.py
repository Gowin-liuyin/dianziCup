"""Read the exact authorized parent and source identities without writing business state."""

import hashlib
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

import httpx
from redis import Redis
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool

RUN = Path(__file__).parent


def main() -> None:
    started = datetime.now(UTC).astimezone().isoformat()
    parent = make_url(os.environ["R06_PHASE_PARENT_DATABASE_URL"])
    if parent.host != "127.0.0.1" or parent.port != 25432:
        raise ValueError("parent identity differs")
    engine = create_engine(parent, poolclass=NullPool, hide_parameters=True)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            source_rows = connection.execute(
                text("SELECT oid,datname,shobj_description(oid,'pg_database') "
                     "FROM pg_database WHERE oid IN (10451302,10434264) ORDER BY oid")
            ).all()
        source_identity = {int(oid): (name, marker) for oid, name, marker in source_rows}
        name, marker = source_identity[10451302]
        if name != "test_dianzi_r06_912_20261017_f15191e6ea74" or not isinstance(marker, str):
            raise ValueError("source native identity differs")
        marker_digest = hashlib.sha256(marker.encode()).hexdigest()
        if marker_digest != "cae93d1ce7798f01a8e370f8dfa99128a83038cdb978b5d321cfa8fd18022c14":
            raise ValueError("source marker differs")
        source_engine = create_engine(parent.set(database=name), poolclass=NullPool,
                                      hide_parameters=True)
        try:
            with source_engine.connect() as connection:
                version = connection.scalar(text("SELECT version_num FROM public.alembic_version"))
                if version != "0030_revalidation_actor_bindings":
                    raise ValueError("source schema differs")
        finally:
            source_engine.dispose()
    finally:
        engine.dispose()
    redis_url = os.environ["R06_PHASE_PARENT_REDIS_URL"].rsplit("/", 1)[0] + "/15"
    cache = Redis.from_url(redis_url, socket_connect_timeout=2, socket_timeout=2)
    try:
        if not cache.ping():
            raise ValueError("cache unavailable")
        own_keys = []
        for key in cache.scan_iter(match="r06-nine-script-20261016:*", count=100):
            own_keys.append(key)
            if len(own_keys) > 32:
                raise ValueError("source namespace not empty")
        if own_keys:
            raise ValueError("source namespace not empty")
    finally:
        cache.close()
    with httpx.Client(timeout=2, trust_env=False) as client:
        health = client.get("http://127.0.0.1:29200/_cluster/health")
        health.raise_for_status()
        if health.json().get("status") not in {"green", "yellow"}:
            raise ValueError("search unavailable")
    record = {
        "started_at": started,
        "ended_at": datetime.now(UTC).astimezone().isoformat(),
        "parent_database_reachable": True,
        "source_oid": 10451302,
        "other_protected_source_oid": 10434264,
        "source_marker_sha256": marker_digest,
        "source_schema": version,
        "redis_database": 15,
        "own_source_namespace_empty": True,
        "opensearch_reachable": True,
        "business_state_writes": 0,
        "paid_calls": 0,
    }
    with (RUN / "actual_resource_probe.json").open("x", encoding="utf-8") as stream:
        json.dump(record, stream, indent=2)
        stream.write("\n")
    print(json.dumps(record))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(json.dumps({"verified": False, "error_type": type(error).__name__,
                          "failure_label": "authorized_resource_probe_failed"}))
        sys.exit(1)
