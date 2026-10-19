"""Read the unique parent sampler's native lock observations without another PG connection."""

import hashlib
import json
import os
import time
from pathlib import Path

LOCK_QUERY = (
    "SELECT EXISTS (SELECT 1 FROM pg_stat_activity "
    "WHERE wait_event_type = 'Lock' "
    "AND :owner_pid = ANY(pg_blocking_pids(pid)))"
)


def publish_lock_snapshot(path, *, run_id, database, marker_sha256, sampler_pid, rows):
    """Publish rows from the already-open parent sampler; this function has no DB API."""
    value = {
        "version": 1,
        "run_id": run_id,
        "database": database,
        "marker_sha256": marker_sha256,
        "sampler_pid": sampler_pid,
        "sampled_monotonic_ns": time.monotonic_ns(),
        "rows": [
            {"pid": row[0], "wait_event_type": row[6], "blocking_pids": row[7]}
            for row in rows if row[1] == database
        ],
    }
    target = Path(path)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(json.dumps(value, separators=(",", ":")), encoding="utf-8")
    os.replace(temporary, target)


class ParentLockObservation:
    def __enter__(self):
        return self

    def __exit__(self, *_exception):
        return False

    def scalar(self, statement, parameters):
        if str(statement) != LOCK_QUERY or set(parameters) != {"owner_pid"}:
            raise RuntimeError("parent_observer_rejects_non_frozen_query")
        owner_pid = parameters["owner_pid"]
        if type(owner_pid) is not int or owner_pid <= 0:
            raise RuntimeError("parent_observer_rejects_invalid_owner_pid")
        value = json.loads(Path(os.environ["R18_PARENT_LOCK_SNAPSHOT"]).read_bytes())
        expected = (
            1,
            os.environ["DIANZI_TEST_RUN_ID"],
            os.environ["R18_REVIEW_DATABASE"],
            os.environ["R18_REVIEW_MARKER_SHA256"],
        )
        observed = tuple(value[key] for key in ("version", "run_id", "database", "marker_sha256"))
        if observed != expected:
            raise RuntimeError("parent_observer_snapshot_identity_mismatch")
        age_ns = time.monotonic_ns() - value["sampled_monotonic_ns"]
        if not 0 <= age_ns <= 2_000_000_000:
            raise RuntimeError("parent_observer_snapshot_stale")
        rows = value["rows"]
        if type(value["sampler_pid"]) is not int or len({row["pid"] for row in rows}) != len(rows):
            raise RuntimeError("parent_observer_invalid_native_rows")
        for row in rows:
            if type(row["pid"]) is not int or not isinstance(row["blocking_pids"], list):
                raise RuntimeError("parent_observer_invalid_native_rows")
            if any(type(pid) is not int or pid <= 0 for pid in row["blocking_pids"]):
                raise RuntimeError("parent_observer_invalid_native_rows")
        blocked = any(
            row["wait_event_type"] == "Lock" and owner_pid in row["blocking_pids"]
            for row in rows
        )
        with Path(os.environ["R18_PARENT_LOCK_READ_RECEIPT"]).open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({
                "query_sha256": hashlib.sha256(LOCK_QUERY.encode()).hexdigest(),
                "owner_pid": owner_pid, "sampler_pid": value["sampler_pid"],
                "sampled_monotonic_ns": value["sampled_monotonic_ns"],
                "age_ns": age_ns, "blocked": blocked,
            }, separators=(",", ":")) + "\n")
        return blocked


def parent_lock_observation(_engine):
    return ParentLockObservation()
