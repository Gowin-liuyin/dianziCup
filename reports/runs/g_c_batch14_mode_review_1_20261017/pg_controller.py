"""Native exact-nine marker controller for this review's single nonce PostgreSQL database."""

import hashlib
import json
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg import sql

import review_checks

ROOT, RUN = review_checks.ROOT, review_checks.RUN
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "backend/src"))
from tests.integration.test_r01_migration_engine_disposal_pg import load_parent_url

DEFAULT_ONLY = "--default-only" in sys.argv
FIXED_RECHECK = "--fixed-recheck" in sys.argv
MAXIMUM_SECONDS = 60 if DEFAULT_ONLY or FIXED_RECHECK else 240
LABEL = "recheck_modes_and_default" if FIXED_RECHECK else ("supplement_default" if DEFAULT_ONLY else "pg_modes_and_default")
RECEIPT = "recheck_pg_controller.command.json" if FIXED_RECHECK else ("supplement_pg_controller.command.json" if DEFAULT_ONLY else "pg_controller.command.json")
NONCE = uuid4().hex[:14]
DATABASE = "test_dianzi_r06_mode_" + NONCE
RUN_ID = "r06_mode_" + NONCE
MARKER_FIELDS = {"project", "kind", "run_id", "owner", "product_sha", "maximum_seconds", "queue", "redis_prefix", "created_at"}


def main():
    if (RUN / RECEIPT).exists() or (RUN / (LABEL + ".xml")).exists():
        raise RuntimeError("refusing PG evidence overwrite")
    started, tick = review_checks.checks.now(), time.monotonic()
    control, chain = review_checks.checks.metadata.control_root(review_checks.checks.metadata.current_identity())
    initial_tree = review_checks.checks.metadata.descendants(control)
    parent = load_parent_url()
    parent_dsn = parent.set(drivername="postgresql").render_as_string(hide_password=False)
    target_url = parent.set(database=DATABASE, drivername="postgresql+psycopg", query={})
    target_dsn = target_url.render_as_string(hide_password=False)
    assert re.fullmatch(r"test_dianzi_r06_mode_[a-f0-9]{14}", DATABASE)
    marker = json.dumps({"project": "dianzi", "kind": "isolated_live_source_observation", "run_id": RUN_ID, "owner": "g_c_batch14_mode_review_1:" + NONCE, "product_sha": review_checks.checks.QUALIFIED, "maximum_seconds": MAXIMUM_SECONDS, "queue": "not_used", "redis_prefix": "not_used", "created_at": review_checks.checks.now()}, separators=(",", ":"))
    result = {"started_at": started, "source_sha": review_checks.checks.QUALIFIED, "database": DATABASE, "nonce": NONCE, "marker_contract": "native exact9 retained from reviewed controller; integration probe is not source live", "maximum_seconds": MAXIMUM_SECONDS, "soft_business_connection_budget": 2, "total_owned_connection_budget_including_parent_sampler": 3, "process_cap_combined_windows_linux": 16, "model_source_paid_requests": 0, "redis_minio_docker_started": 0, "control_chain": chain, "samples": [], "errors": [], "test_exit_code": None, "owned_database_dropped": False}
    owned_oid = None
    child = None
    exit_code = 1
    with psycopg.connect(parent_dsn, connect_timeout=3, autocommit=True, application_name="gc_mode_review_parent_control") as admin:
        identity = admin.execute("SELECT current_database(),current_user,pg_backend_pid(),(SELECT backend_start::text FROM pg_stat_activity WHERE pid=pg_backend_pid()),(SELECT rolsuper FROM pg_roles WHERE rolname=current_user),(SELECT rolconnlimit FROM pg_roles WHERE rolname=current_user),(SELECT setting FROM pg_settings WHERE name='max_connections')").fetchone()
        assert identity[:2] == ("test_dianzi_r01_20261014", "test_dianzi_r01")
        result["parent_control"] = {"database": identity[0], "username": identity[1], "backend_pid": identity[2], "backend_birth": identity[3], "superuser": identity[4], "role_connection_limit": identity[5], "server_max_connections": int(identity[6]), "profile_two_is_soft_not_physical_or_total": True, "phase": "native_database_create_and_sampler", "creating_allowlisted_caller": "pg_controller.main via frozen load_parent_url; DPAPI stdout memory-only"}
        bindings = admin.execute("SELECT datname,oid,pg_get_userbyid(datdba),shobj_description(oid,'pg_database') FROM pg_catalog.pg_database WHERE oid IN (10451302,10434264) ORDER BY oid").fetchall()
        result["source_bindings_before"] = [{"database": row[0], "oid": row[1], "owner": row[2], "comment_sha256": hashlib.sha256((row[3] or "").encode()).hexdigest()} for row in bindings]
        try:
            assert admin.execute("SELECT oid FROM pg_database WHERE datname=%s", (DATABASE,)).fetchone() is None
            admin.execute(sql.SQL("CREATE DATABASE {} OWNER {}").format(sql.Identifier(DATABASE), sql.Identifier("test_dianzi_r01")))
            owned_oid = admin.execute("SELECT oid FROM pg_database WHERE datname=%s", (DATABASE,)).fetchone()[0]
            admin.execute(sql.SQL("COMMENT ON DATABASE {} IS {}").format(sql.Identifier(DATABASE), sql.Literal(marker)))
            native_oid, native_owner, native_comment = admin.execute("SELECT oid,pg_get_userbyid(datdba),shobj_description(oid,'pg_database') FROM pg_database WHERE datname=%s", (DATABASE,)).fetchone()
            assert native_oid == owned_oid and native_owner == "test_dianzi_r01" and native_comment == marker
            assert set(json.loads(native_comment)) == MARKER_FIELDS
            result["native_identity"] = {"oid": native_oid, "owner": native_owner, "comment": native_comment, "comment_sha256": hashlib.sha256(native_comment.encode()).hexdigest(), "exact_nine_fields": True}
            env = review_checks.checks.environment()
            env.update(TEST_DATABASE_URL=target_dsn, DIANZI_TEST_RUN_ID=RUN_ID, R06_MODE_DATABASE_OID=str(owned_oid), R06_MODE_DATABASE_COMMENT_SHA256=result["native_identity"]["comment_sha256"])
            if FIXED_RECHECK:
                env["R06_MODE_BACKEND_LOG_LABEL"] = "recheck_pg_backend_creation.jsonl"
            env["PYTHONPATH"] = os.pathsep.join([str(ROOT / "backend"), str(ROOT / "backend/src"), str(ROOT), str(ROOT / "backend/tests/unit"), str(ROOT / "backend/tests/integration"), str(RUN)])
            selected = [] if DEFAULT_ONLY else ([str(RUN / "test_fixed_revision_mode_read_pg.py")] if FIXED_RECHECK else ["tests/integration/test_r06_revision_mode_read_pg.py"])
            if FIXED_RECHECK:
                result["test_source_sha"] = "6bb19fcdbf5c8242142c3f61e338b98a29bc5501"
                result["test_material_sha"] = "81840ea42ae1425dfa1468eafed7edb49b440357"
                result["copied_test_sha256"] = hashlib.sha256((RUN / "test_fixed_revision_mode_read_pg.py").read_bytes()).hexdigest()
            command = [review_checks.checks.PYTHON, "-m", "pytest", "-p", "pg_backend_plugin", *selected, str(RUN / "test_default_mode_pg.py"), "--no-cov", "-q", "--junitxml=" + str(RUN / (LABEL + ".xml"))]
            result["command"] = command
            result["cwd"] = str(ROOT / "backend")
            with (RUN / (LABEL + ".stdout.log")).open("wb") as stdout, (RUN / (LABEL + ".stderr.log")).open("wb") as stderr:
                child = subprocess.Popen(command, cwd=ROOT / "backend", env=env, stdout=stdout, stderr=stderr)
                while child.poll() is None:
                    rows = admin.execute("SELECT pid,datname,usename,application_name,backend_start::text,state FROM pg_stat_activity WHERE backend_type='client backend' ORDER BY pid").fetchall()
                    target_rows = [row for row in rows if row[1] == DATABASE]
                    tree = review_checks.checks.metadata.descendants(control)
                    sample = {"at": review_checks.checks.now(), "phase": "mode_tests_and_default_routes", "parent_sampler_pid": identity[2], "target_rows": target_rows, "target_connection_count": len(target_rows), "target_plus_parent_sampler_count": len(target_rows) + 1, "all_server_client_rows": rows, "all_server_client_count": len(rows), "windows_owned": list(tree.values()), "linux_owned": [], "combined_process_count": len(tree)}
                    result["samples"].append(sample)
                    if len(target_rows) > 2 or len(tree) > 16 or time.monotonic() - tick >= MAXIMUM_SECONDS - 10:
                        result["errors"].append("owned_connection_process_or_deadline_bound_exceeded")
                        child.terminate()
                        break
                    time.sleep(0.05)
                exit_code = child.wait(timeout=5)
            result["test_exit_code"] = exit_code
        except Exception as error:
            result["errors"].append({"type": type(error).__name__, "details": "withheld"})
            if child is not None and child.poll() is None:
                child.terminate()
                child.wait(timeout=5)
        finally:
            rows = admin.execute("SELECT pid,datname,usename,application_name,backend_start::text,state FROM pg_stat_activity WHERE backend_type='client backend' ORDER BY pid").fetchall()
            remaining = [row for row in rows if row[1] == DATABASE]
            result["cleanup_before_drop"] = {"at": review_checks.checks.now(), "target_sessions": remaining, "parent_sampler_pid": identity[2], "all_server_client_rows": rows, "all_server_client_count_including_sampler": len(rows)}
            if owned_oid is not None:
                actual = admin.execute("SELECT oid,shobj_description(oid,'pg_database') FROM pg_database WHERE datname=%s", (DATABASE,)).fetchone()
                assert actual == (owned_oid, marker) and not remaining
                admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(DATABASE)))
                assert admin.execute("SELECT oid FROM pg_database WHERE datname=%s", (DATABASE,)).fetchone() is None
                result["owned_database_dropped"] = True
            bindings = admin.execute("SELECT datname,oid,pg_get_userbyid(datdba),shobj_description(oid,'pg_database') FROM pg_catalog.pg_database WHERE oid IN (10451302,10434264) ORDER BY oid").fetchall()
            result["source_bindings_after"] = [{"database": row[0], "oid": row[1], "owner": row[2], "comment_sha256": hashlib.sha256((row[3] or "").encode()).hexdigest()} for row in bindings]
            assert result["source_bindings_after"] == result["source_bindings_before"]
    result["parent_connection_closed"] = True
    result["ended_at"] = review_checks.checks.now()
    result["wall_seconds"] = time.monotonic() - tick
    result["combined_process_peak"] = max((row["combined_process_count"] for row in result["samples"]), default=0)
    result["target_connection_peak"] = max((row["target_connection_count"] for row in result["samples"]), default=0)
    result["target_plus_parent_sampler_peak"] = max((row["target_plus_parent_sampler_count"] for row in result["samples"]), default=0)
    leftovers = review_checks.checks.metadata.descendants(control)
    result["remaining_owned_children"] = [row for pid, row in leftovers.items() if pid not in initial_tree]
    forbidden = (parent_dsn, target_dsn, parent.password or "")
    fragments = {(parent.password or "")[offset:offset + 8] for offset in range(max(0, len(parent.password or "") - 7))}
    hits = []
    for path in RUN.rglob("*"):
        if path.is_file():
            raw = path.read_bytes()
            if any(value and value.encode() in raw for value in forbidden) or any(fragment.encode() in raw for fragment in fragments):
                hits.append(str(path.relative_to(RUN)))
    result["secret_scan"] = {"exact_dsn_password_or_8char_fragment_hits": hits, "plaintext_reference_written": False}
    (RUN / RECEIPT).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("started_at", "ended_at", "wall_seconds", "test_exit_code", "combined_process_peak", "target_connection_peak", "target_plus_parent_sampler_peak", "owned_database_dropped", "errors", "secret_scan")}), flush=True)
    raise SystemExit(exit_code or bool(result["errors"] or hits or result["remaining_owned_children"]))


if __name__ == "__main__":
    main()
